/* Tests du serveur Arpagon : node --test tests/
   Base D1 simulée avec SQLite intégré à Node, Stripe et Resend simulés. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { webcrypto } from "node:crypto";
import worker from "../server/worker.js";

/* ---------- D1 simulée ---------- */
function makeD1() {
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(new URL("../server/schema.sql", import.meta.url), "utf8"));
  const stmt = (sql) => {
    let args = [];
    const s = {
      bind: (...a) => { args = a.map((x) => (x === undefined ? null : x)); return s; },
      first: async () => db.prepare(sql).get(...args) || null,
      all: async () => ({ results: db.prepare(sql).all(...args) }),
      run: async () => { db.prepare(sql).run(...args); return { success: true }; },
    };
    return s;
  };
  return { prepare: stmt, batch: async (list) => { for (const s of list) await s.run(); }, raw: db };
}

const ORIGIN = "https://mouadjabiera06-jpg.github.io";
function makeEnv() {
  return {
    DB: makeD1(),
    APP_URL: ORIGIN + "/arpagon/",
    APP_ORIGINS: ORIGIN,
    PRICE_MONTHLY: "price_m",
    PRICE_YEARLY: "price_y",
    MAIL_FROM: "Arpagon <test@example.com>",
    STRIPE_SECRET: "sk_test_x",
    STRIPE_WEBHOOK_SECRET: "whsec_test",
    RESEND_KEY: "re_x",
    DATA_KEY: Buffer.from(webcrypto.getRandomValues(new Uint8Array(32))).toString("base64"),
  };
}

/* ---------- services externes simulés ---------- */
const sent = [], stripeCalls = [];
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, opts = {}) => {
  url = String(url);
  if (url.startsWith("https://api.resend.com")) { sent.push(JSON.parse(opts.body)); return new Response("{}", { status: 200 }); }
  if (url.startsWith("https://api.stripe.com")) {
    stripeCalls.push({ url, method: opts.method, body: opts.body });
    if (url.endsWith("/checkout/sessions")) return Response.json({ url: "https://checkout.stripe.com/c/test" });
    if (url.includes("/billing_portal/sessions")) return Response.json({ url: "https://billing.stripe.com/p/test" });
    if (url.includes("/subscriptions/")) return Response.json({ id: "sub_1", customer: "cus_1", status: "active", metadata: {},
      items: { data: [{ price: { id: "price_y" }, current_period_end: 1900000000 }] }, cancel_at_period_end: false });
    return Response.json({});
  }
  return realFetch(url, opts);
};

function call(env, method, path, { body, token, origin = ORIGIN, headers = {} } = {}) {
  const h = { ...headers };
  if (origin) h.Origin = origin;
  if (token) h.Authorization = "Bearer " + token;
  if (body !== undefined && typeof body !== "string") h["Content-Type"] = "application/json";
  return worker.fetch(new Request("https://api.test" + path, {
    method, headers: h, body: body === undefined ? undefined : typeof body === "string" ? body : JSON.stringify(body),
  }), env);
}
async function login(env, email = "mouad@example.com") {
  sent.length = 0;
  const r = await call(env, "POST", "/auth/request", { body: { email } });
  assert.equal(r.status, 200);
  const link = sent[0].html.match(/#login=([A-Za-z0-9_-]+)/)[1];
  const v = await call(env, "POST", "/auth/verify", { body: { token: link } });
  assert.equal(v.status, 200);
  return { ...(await v.json()), link };
}
async function signedWebhook(env, event) {
  const payload = JSON.stringify(event), t = Math.floor(Date.now() / 1000);
  const key = await webcrypto.subtle.importKey("raw", new TextEncoder().encode(env.STRIPE_WEBHOOK_SECRET), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = Buffer.from(await webcrypto.subtle.sign("HMAC", key, new TextEncoder().encode(t + "." + payload))).toString("hex");
  return call(env, "POST", "/stripe/webhook", { body: payload, origin: null, headers: { "Stripe-Signature": `t=${t},v1=${sig}` } });
}

/* ---------- tests ---------- */
test("origine inconnue refusée", async () => {
  const r = await call(makeEnv(), "POST", "/auth/request", { body: { email: "a@b.fr" }, origin: "https://pirate.example" });
  assert.equal(r.status, 403);
});

test("lien magique : connexion, usage unique, e-mail invalide", async () => {
  const env = makeEnv();
  assert.equal((await call(env, "POST", "/auth/request", { body: { email: "pas-un-mail" } })).status, 400);
  const { session, me, link } = await login(env);
  assert.ok(session.length > 30);
  assert.equal(me.email, "mouad@example.com");
  assert.equal(me.premium, false);
  const again = await call(env, "POST", "/auth/verify", { body: { token: link } });
  assert.equal(again.status, 400, "un lien ne sert qu'une fois");
  const row = env.DB.raw.prepare("SELECT * FROM login_tokens").get();
  assert.notEqual(row.hash, link, "seule l'empreinte est stockée");
});

test("limitation : 6e demande de lien dans l'heure refusée", async () => {
  const env = makeEnv();
  for (let i = 0; i < 5; i++) assert.equal((await call(env, "POST", "/auth/request", { body: { email: "x@y.fr" } })).status, 200);
  assert.equal((await call(env, "POST", "/auth/request", { body: { email: "x@y.fr" } })).status, 429);
});

test("sauvegarde réservée au premium", async () => {
  const env = makeEnv();
  const { session } = await login(env);
  assert.equal((await call(env, "GET", "/backup", { token: session })).status, 402);
  assert.equal((await call(env, "GET", "/me")).status, 401);
});

test("paiement : CGV obligatoires, puis Checkout, webhook signé, premium actif", async () => {
  const env = makeEnv();
  const { session } = await login(env);
  assert.equal((await call(env, "POST", "/billing/checkout", { token: session, body: { plan: "yearly" } })).status, 400);
  const c = await call(env, "POST", "/billing/checkout", { token: session, body: { plan: "yearly", acceptCgv: true } });
  assert.equal((await c.json()).url, "https://checkout.stripe.com/c/test");
  assert.match(stripeCalls.at(-1).body, /price%5D=price_y/);

  const uid = env.DB.raw.prepare("SELECT id FROM users").get().id;
  const bad = await call(env, "POST", "/stripe/webhook", { body: "{}", origin: null, headers: { "Stripe-Signature": "t=1,v1=00" } });
  assert.equal(bad.status, 400, "signature invalide refusée");
  const ok = await signedWebhook(env, { id: "evt_1", type: "checkout.session.completed",
    data: { object: { mode: "subscription", client_reference_id: uid, customer: "cus_1", subscription: "sub_1" } } });
  assert.equal(ok.status, 200);
  const me = (await (await call(env, "GET", "/me", { token: session })).json()).me;
  assert.equal(me.premium, true);
  assert.equal(me.plan, "yearly");
  assert.equal(me.periodEnd, 1900000000);

  const portal = await call(env, "POST", "/billing/portal", { token: session });
  assert.equal((await portal.json()).url, "https://billing.stripe.com/p/test");

  /* Résiliation reçue par webhook : plus premium */
  await signedWebhook(env, { id: "evt_2", type: "customer.subscription.deleted",
    data: { object: { id: "sub_1", customer: "cus_1", status: "canceled", metadata: {}, items: { data: [] } } } });
  assert.equal((await (await call(env, "GET", "/me", { token: session })).json()).me.premium, false);
});

test("sauvegarde chiffrée, conflit entre appareils, suppression du compte", async () => {
  const env = makeEnv();
  const { session } = await login(env);
  env.DB.raw.prepare("UPDATE users SET sub_status = 'active', sub_id = 'sub_1', stripe_customer = 'cus_1'").run();
  const data = { v: 1, data: { main: { transactions: [{ note: "Loyer secret" }] } } };

  const p1 = await (await call(env, "PUT", "/backup", { token: session, body: { data, base: null } })).json();
  const stored = env.DB.raw.prepare("SELECT data FROM backups").get().data;
  assert.ok(!stored.includes("Loyer"), "rien en clair dans la base");

  const g = await (await call(env, "GET", "/backup", { token: session })).json();
  assert.equal(g.data.data.main.transactions[0].note, "Loyer secret");
  assert.equal(g.updatedAt, p1.updatedAt);

  const second = await login(env);  // 2e appareil
  const p2 = await call(env, "PUT", "/backup", { token: second.session, body: { data, base: p1.updatedAt } });
  assert.equal(p2.status, 200);
  const stale = await call(env, "PUT", "/backup", { token: session, body: { data, base: p1.updatedAt } });
  assert.equal(stale.status, 409, "le 1er appareil est en retard : conflit");
  assert.equal((await call(env, "PUT", "/backup", { token: session, body: { data, base: p1.updatedAt, force: true } })).status, 200);

  const del = await call(env, "DELETE", "/account", { token: session });
  assert.equal((await del.json()).deleted, true);
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) n FROM users").get().n, 0);
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) n FROM backups").get().n, 0);
  assert.ok(stripeCalls.some((c) => c.method === "DELETE" && c.url.endsWith("/subscriptions/sub_1")), "abonnement résilié chez Stripe");
});
