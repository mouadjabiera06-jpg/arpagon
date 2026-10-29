/* =====================================================================
   Serveur Arpagon — Cloudflare Worker + base D1
   - Connexion par lien magique envoyé par e-mail (aucun mot de passe)
   - Sauvegarde en ligne chiffrée (AES-GCM) réservée au Premium
   - Abonnement Stripe : Checkout, webhooks signés, portail client
   - Suppression du compte (RGPD)

   Secrets (npx wrangler secret put NOM) :
     STRIPE_SECRET          clé secrète Stripe (sk_test_… puis sk_live_…)
     STRIPE_WEBHOOK_SECRET  secret de signature du webhook (whsec_…)
     RESEND_KEY             clé API Resend (envoi des e-mails)
     DATA_KEY               32 octets aléatoires en base64 (chiffrement)
   Variables (wrangler.toml) :
     APP_URL                adresse publique de l'app (se termine par /)
     APP_ORIGINS            origines autorisées, séparées par des virgules
     PRICE_MONTHLY          identifiant du prix mensuel Stripe (price_…)
     PRICE_YEARLY           identifiant du prix annuel Stripe (price_…)
     PRICE_FOUNDER_MONTHLY  prix « fondateur » mensuel (facultatif)
     PRICE_FOUNDER_YEARLY   prix « fondateur » annuel (facultatif)
     FOUNDER_LIMIT          nombre de places au prix fondateur (ex. 100)
     TRIAL_DAYS             jours d'essai offerts au premier abonnement (ex. 14, 0 = aucun)
     MAIL_FROM              expéditeur, ex. "Arpagon <connexion@ton-domaine.fr>"
   ===================================================================== */

const MAX_BACKUP = 2 * 1024 * 1024;           // 2 Mo par sauvegarde
const SESSION_DAYS = 90;
const LOGIN_MINUTES = 15;
const PREMIUM_STATUSES = ["active", "trialing", "past_due"];

/* Adresses des services externes (remplaçables pour les tests) */
const STRIPE_API = "https://api.stripe.com/v1";
const RESEND_API = "https://api.resend.com/emails";

/* ---------- outils ---------- */
const now = () => Math.floor(Date.now() / 1000);
const enc = new TextEncoder();

function b64url(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function b64(bytes) { let s = ""; for (const b of bytes) s += String.fromCharCode(b); return btoa(s); }
function unb64(s) { return Uint8Array.from(atob(s), (c) => c.charCodeAt(0)); }
function randomToken() { return b64url(crypto.getRandomValues(new Uint8Array(32))); }
async function sha256(s) {
  const h = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
function validEmail(e) {
  return typeof e === "string" && e.length <= 254 && /^[^\s@<>"]+@[^\s@<>"]+\.[^\s@<>"]{2,}$/.test(e);
}
function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

/* ---------- réponses + CORS ---------- */
function allowedOrigin(req, env) {
  const o = req.headers.get("Origin") || "";
  const list = String(env.APP_ORIGINS || "").split(",").map((x) => x.trim()).filter(Boolean);
  return list.includes(o) ? o : "";
}
function cors(req, env) {
  const o = allowedOrigin(req, env);
  if (!o) return {};
  return {
    "Access-Control-Allow-Origin": o,
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}
function json(req, env, data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...cors(req, env) },
  });
}
const fail = (req, env, code, status) => json(req, env, { error: code }, status);

/* ---------- limitation de débit ---------- */
async function limited(env, key, max, windowSec) {
  const t = now();
  const row = await env.DB.prepare("SELECT count, reset FROM rate WHERE key = ?").bind(key).first();
  if (!row || row.reset <= t) {
    await env.DB.prepare("INSERT OR REPLACE INTO rate (key, count, reset) VALUES (?, 1, ?)").bind(key, t + windowSec).run();
    return false;
  }
  if (row.count >= max) return true;
  await env.DB.prepare("UPDATE rate SET count = count + 1 WHERE key = ?").bind(key).run();
  return false;
}

/* ---------- chiffrement des sauvegardes ---------- */
let keyCache = null;
async function dataKey(env) {
  if (keyCache) return keyCache;
  const raw = unb64(env.DATA_KEY || "");
  if (raw.length !== 32) throw new Error("DATA_KEY doit faire 32 octets en base64");
  keyCache = await crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
  return keyCache;
}
async function seal(env, userId, text) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: enc.encode(userId) }, await dataKey(env), enc.encode(text));
  return { iv: b64(iv), data: b64(new Uint8Array(ct)) };
}
async function open(env, userId, iv, data) {
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(iv), additionalData: enc.encode(userId) }, await dataKey(env), unb64(data));
  return new TextDecoder().decode(pt);
}

/* ---------- utilisateur courant ---------- */
async function currentUser(req, env) {
  const h = req.headers.get("Authorization") || "";
  const m = h.match(/^Bearer ([A-Za-z0-9_-]{20,100})$/);
  if (!m) return null;
  const row = await env.DB.prepare(
    "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.hash = ? AND s.expires > ?"
  ).bind(await sha256(m[1]), now()).first();
  return row || null;
}
function isPremium(u) { return !!u && PREMIUM_STATUSES.includes(u.sub_status); }
function meOf(u) {
  return {
    email: u.email,
    premium: isPremium(u),
    status: u.sub_status || null,
    plan: u.plan || null,
    periodEnd: u.period_end || null,
    cancelAtEnd: !!u.cancel_at_end,
    canTrial: !u.stripe_customer,
    founder: !!u.founder,
  };
}

/* ---------- Stripe ---------- */
function form(obj, prefix = "", out = []) {
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined || v === null) continue;
    const key = prefix ? `${prefix}[${k}]` : k;
    if (typeof v === "object") form(v, key, out);
    else out.push(encodeURIComponent(key) + "=" + encodeURIComponent(String(v)));
  }
  return out.join("&");
}
async function stripe(env, method, path, body) {
  const r = await fetch((env.STRIPE_API || STRIPE_API) + path, {
    method,
    headers: { Authorization: "Bearer " + env.STRIPE_SECRET, "Content-Type": "application/x-www-form-urlencoded" },
    body: body ? form(body) : undefined,
  });
  const j = await r.json();
  if (!r.ok) throw new Error("stripe: " + ((j.error && j.error.message) || r.status));
  return j;
}
async function verifyStripeSignature(env, payload, header) {
  const parts = Object.fromEntries(
    String(header || "").split(",").map((p) => p.split("=")).filter((p) => p.length === 2).map(([k, v]) => [k.trim(), v.trim()])
  );
  const sigs = String(header || "").split(",").filter((p) => p.trim().startsWith("v1=")).map((p) => p.trim().slice(3));
  const t = Number(parts.t);
  if (!t || !sigs.length || Math.abs(now() - t) > 300) return false;
  const key = await crypto.subtle.importKey("raw", enc.encode(env.STRIPE_WEBHOOK_SECRET || ""), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(t + "." + payload));
  const hex = [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return sigs.some((s) => timingSafeEqual(s, hex));
}
/* La fin de période a changé de place selon la version de l'API Stripe */
function periodEndOf(sub) {
  if (sub.current_period_end) return sub.current_period_end;
  const it = sub.items && sub.items.data && sub.items.data[0];
  return (it && it.current_period_end) || null;
}
function planOf(env, sub) {
  const it = sub.items && sub.items.data && sub.items.data[0];
  const price = it && it.price && it.price.id;
  if (!price) return null;
  if (price === env.PRICE_YEARLY || price === env.PRICE_FOUNDER_YEARLY) return "yearly";
  if (price === env.PRICE_MONTHLY || price === env.PRICE_FOUNDER_MONTHLY) return "monthly";
  return null;
}
function isFounderPrice(env, sub) {
  const it = sub.items && sub.items.data && sub.items.data[0];
  const price = it && it.price && it.price.id;
  return !!price && (price === env.PRICE_FOUNDER_MONTHLY || price === env.PRICE_FOUNDER_YEARLY);
}
/* Places restantes au prix fondateur (0 si l'offre n'est pas configurée) */
async function founderLeft(env) {
  const limit = Number(env.FOUNDER_LIMIT || 0);
  if (!limit || !env.PRICE_FOUNDER_MONTHLY || !env.PRICE_FOUNDER_YEARLY) return 0;
  const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM users WHERE founder = 1").first();
  return Math.max(0, limit - ((row && row.n) || 0));
}
async function applySubscription(env, sub, userIdHint) {
  let user = null;
  const uid = userIdHint || (sub.metadata && sub.metadata.user_id);
  if (uid) user = await env.DB.prepare("SELECT id FROM users WHERE id = ?").bind(uid).first();
  if (!user && sub.customer) user = await env.DB.prepare("SELECT id FROM users WHERE stripe_customer = ?").bind(sub.customer).first();
  if (!user) return;
  await env.DB.prepare(
    "UPDATE users SET stripe_customer = ?, sub_id = ?, sub_status = ?, plan = ?, period_end = ?, cancel_at_end = ?, founder = MAX(founder, ?) WHERE id = ?"
  ).bind(sub.customer || null, sub.id, sub.status, planOf(env, sub), periodEndOf(sub), sub.cancel_at_period_end ? 1 : 0,
    isFounderPrice(env, sub) ? 1 : 0, user.id).run();
}

/* ---------- e-mail ---------- */
async function sendLoginMail(env, email, link) {
  const html =
    '<div style="font-family:Georgia,serif;max-width:480px;margin:auto;padding:24px;color:#3A2B1B">' +
    '<h2 style="margin:0 0 12px">Connexion à Arpagon</h2>' +
    "<p>Clique sur le bouton pour te connecter. Le lien est valable " + LOGIN_MINUTES + " minutes et ne sert qu'une fois.</p>" +
    '<p style="margin:24px 0"><a href="' + link + '" style="background:#C1782A;color:#fff;padding:12px 20px;border-radius:10px;text-decoration:none">Me connecter</a></p>' +
    '<p style="font-size:13px;color:#6E5A42">Tu n\'as rien demandé ? Ignore ce message, personne ne pourra se connecter sans ce lien.</p></div>';
  const r = await fetch(env.RESEND_API || RESEND_API, {
    method: "POST",
    headers: { Authorization: "Bearer " + env.RESEND_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ from: env.MAIL_FROM, to: [email], subject: "Ton lien de connexion Arpagon", html }),
  });
  if (!r.ok) throw new Error("mail_" + r.status);
}

/* ---------- routes ---------- */
async function readJson(req, max = 64 * 1024) {
  const text = await req.text();
  if (text.length > max) { const e = new Error("too_large"); e.status = 413; throw e; }
  try { return text ? JSON.parse(text) : {}; } catch { const e = new Error("bad_json"); e.status = 400; throw e; }
}

async function route(req, env) {
  const url = new URL(req.url);
  const p = url.pathname.replace(/\/+$/, "") || "/";
  const M = req.method;
  const ip = req.headers.get("CF-Connecting-IP") || "local";

  if (M === "OPTIONS") return new Response(null, { status: 204, headers: cors(req, env) });
  if (p === "/" && M === "GET") return json(req, env, { ok: true, service: "arpagon" });

  /* Webhook Stripe : pas de CORS, signature obligatoire */
  if (p === "/stripe/webhook" && M === "POST") {
    const payload = await req.text();
    if (!(await verifyStripeSignature(env, payload, req.headers.get("Stripe-Signature")))) return new Response("bad signature", { status: 400 });
    const ev = JSON.parse(payload);
    const seen = await env.DB.prepare("SELECT id FROM webhook_events WHERE id = ?").bind(ev.id).first();
    if (seen) return new Response("ok");
    const o = ev.data && ev.data.object;
    if (ev.type === "checkout.session.completed" && o && o.mode === "subscription") {
      const uid = o.client_reference_id;
      if (uid && o.customer) await env.DB.prepare("UPDATE users SET stripe_customer = ? WHERE id = ?").bind(o.customer, uid).run();
      if (o.subscription) await applySubscription(env, await stripe(env, "GET", "/subscriptions/" + o.subscription), uid);
    } else if (/^customer\.subscription\.(created|updated|deleted|paused|resumed)$/.test(ev.type) && o) {
      await applySubscription(env, o);
    }
    await env.DB.prepare("INSERT OR IGNORE INTO webhook_events (id, at) VALUES (?, ?)").bind(ev.id, now()).run();
    return new Response("ok");
  }

  /* Toutes les autres routes viennent de l'app : origine obligatoire */
  if (!allowedOrigin(req, env)) return new Response("origin not allowed", { status: 403 });

  /* --- Offre affichée dans l'app (public) --- */
  if (p === "/offer" && M === "GET") {
    return json(req, env, { founderLeft: await founderLeft(env), trialDays: Number(env.TRIAL_DAYS || 0) });
  }

  /* --- Connexion par lien magique --- */
  if (p === "/auth/request" && M === "POST") {
    const b = await readJson(req);
    const email = String(b.email || "").trim().toLowerCase();
    if (!validEmail(email)) return fail(req, env, "email_invalide", 400);
    if (await limited(env, "ip:" + ip, 20, 3600) || await limited(env, "mail:" + email, 5, 3600)) return fail(req, env, "trop_de_demandes", 429);
    const token = randomToken();
    await env.DB.prepare("INSERT INTO login_tokens (hash, email, expires) VALUES (?, ?, ?)")
      .bind(await sha256(token), email, now() + LOGIN_MINUTES * 60).run();
    await sendLoginMail(env, email, env.APP_URL + "#login=" + token);
    return json(req, env, { sent: true });
  }
  if (p === "/auth/verify" && M === "POST") {
    if (await limited(env, "verify:" + ip, 30, 3600)) return fail(req, env, "trop_de_demandes", 429);
    const b = await readJson(req);
    const hash = await sha256(String(b.token || ""));
    const row = await env.DB.prepare("SELECT email, expires, used FROM login_tokens WHERE hash = ?").bind(hash).first();
    if (!row || row.used || row.expires < now()) return fail(req, env, "lien_expire", 400);
    await env.DB.prepare("UPDATE login_tokens SET used = 1 WHERE hash = ?").bind(hash).run();
    let user = await env.DB.prepare("SELECT * FROM users WHERE email = ?").bind(row.email).first();
    if (!user) {
      const id = crypto.randomUUID();
      await env.DB.prepare("INSERT INTO users (id, email, created_at) VALUES (?, ?, ?)").bind(id, row.email, now()).run();
      user = await env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(id).first();
    }
    const session = randomToken();
    await env.DB.prepare("INSERT INTO sessions (hash, user_id, created_at, expires) VALUES (?, ?, ?, ?)")
      .bind(await sha256(session), user.id, now(), now() + SESSION_DAYS * 86400).run();
    return json(req, env, { session, me: meOf(user) });
  }

  /* --- À partir d'ici : connecté --- */
  const user = await currentUser(req, env);
  if (!user) return fail(req, env, "non_connecte", 401);
  if (await limited(env, "user:" + user.id, 600, 3600)) return fail(req, env, "trop_de_demandes", 429);

  if (p === "/me" && M === "GET") return json(req, env, { me: meOf(user) });

  if (p === "/logout" && M === "POST") {
    const tok = (req.headers.get("Authorization") || "").slice(7);
    await env.DB.prepare("DELETE FROM sessions WHERE hash = ?").bind(await sha256(tok)).run();
    return json(req, env, { ok: true });
  }

  if (p === "/account" && M === "DELETE") {
    if (user.sub_id && PREMIUM_STATUSES.includes(user.sub_status)) await stripe(env, "DELETE", "/subscriptions/" + user.sub_id);
    await env.DB.batch([
      env.DB.prepare("DELETE FROM backups WHERE user_id = ?").bind(user.id),
      env.DB.prepare("DELETE FROM sessions WHERE user_id = ?").bind(user.id),
      env.DB.prepare("DELETE FROM login_tokens WHERE email = ?").bind(user.email),
      env.DB.prepare("DELETE FROM users WHERE id = ?").bind(user.id),
    ]);
    return json(req, env, { deleted: true });
  }

  /* --- Abonnement --- */
  if (p === "/billing/checkout" && M === "POST") {
    const b = await readJson(req);
    if (!b.acceptCgv) return fail(req, env, "cgv_non_acceptees", 400);
    if (isPremium(user)) return fail(req, env, "deja_premium", 409);
    const founder = (await founderLeft(env)) > 0;
    const yearly = b.plan === "yearly";
    const price = founder ? (yearly ? env.PRICE_FOUNDER_YEARLY : env.PRICE_FOUNDER_MONTHLY) : (yearly ? env.PRICE_YEARLY : env.PRICE_MONTHLY);
    const trial = !user.stripe_customer && Number(env.TRIAL_DAYS || 0) > 0 ? Number(env.TRIAL_DAYS) : undefined;
    await env.DB.prepare("UPDATE users SET cgv_at = ? WHERE id = ?").bind(now(), user.id).run();
    const s = await stripe(env, "POST", "/checkout/sessions", {
      mode: "subscription",
      line_items: { 0: { price, quantity: 1 } },
      success_url: env.APP_URL + "#premium=ok",
      cancel_url: env.APP_URL + "#premium=annule",
      client_reference_id: user.id,
      customer: user.stripe_customer || undefined,
      customer_email: user.stripe_customer ? undefined : user.email,
      subscription_data: { metadata: { user_id: user.id }, trial_period_days: trial },
      allow_promotion_codes: "true",
      locale: "fr",
    });
    return json(req, env, { url: s.url });
  }
  if (p === "/billing/portal" && M === "POST") {
    if (!user.stripe_customer) return fail(req, env, "aucun_abonnement", 400);
    const s = await stripe(env, "POST", "/billing_portal/sessions", { customer: user.stripe_customer, return_url: env.APP_URL });
    return json(req, env, { url: s.url });
  }

  /* --- Sauvegarde en ligne (Premium) --- */
  if (p === "/backup") {
    if (!isPremium(user)) return fail(req, env, "premium_requis", 402);
    const row = await env.DB.prepare("SELECT iv, data, updated_at FROM backups WHERE user_id = ?").bind(user.id).first();
    if (M === "GET") {
      if (!row) return json(req, env, { data: null, updatedAt: null });
      if (url.searchParams.get("meta") === "1") return json(req, env, { updatedAt: row.updated_at });
      return json(req, env, { data: JSON.parse(await open(env, user.id, row.iv, row.data)), updatedAt: row.updated_at });
    }
    if (M === "PUT") {
      const b = await readJson(req, MAX_BACKUP + 4096);
      if (!b.data || typeof b.data !== "object") return fail(req, env, "donnees_invalides", 400);
      /* Conflit : un autre appareil a sauvegardé depuis la dernière synchro de celui-ci */
      if (row && !b.force && b.base !== row.updated_at) return json(req, env, { error: "conflit", updatedAt: row.updated_at }, 409);
      const text = JSON.stringify(b.data);
      if (text.length > MAX_BACKUP) return fail(req, env, "sauvegarde_trop_grosse", 413);
      const sealed = await seal(env, user.id, text);
      const t = Math.max(now(), row ? row.updated_at + 1 : 0);
      await env.DB.prepare("INSERT OR REPLACE INTO backups (user_id, iv, data, size, updated_at) VALUES (?, ?, ?, ?, ?)")
        .bind(user.id, sealed.iv, sealed.data, text.length, t).run();
      return json(req, env, { updatedAt: t });
    }
  }

  return fail(req, env, "introuvable", 404);
}

export default {
  async fetch(req, env) {
    try {
      return await route(req, env);
    } catch (e) {
      /* Jamais de données utilisateur dans les journaux : seulement le type d'erreur */
      console.log("erreur", e && e.message ? e.message.slice(0, 120) : "inconnue");
      return fail(req, env, e && e.status ? e.message : "erreur_serveur", (e && e.status) || 500);
    }
  },
  /* Ménage quotidien : jetons et sessions expirés */
  async scheduled(_ev, env) {
    const t = now();
    await env.DB.batch([
      env.DB.prepare("DELETE FROM login_tokens WHERE expires < ?").bind(t - 86400),
      env.DB.prepare("DELETE FROM sessions WHERE expires < ?").bind(t),
      env.DB.prepare("DELETE FROM rate WHERE reset < ?").bind(t),
      env.DB.prepare("DELETE FROM webhook_events WHERE at < ?").bind(t - 30 * 86400),
    ]);
  },
};
