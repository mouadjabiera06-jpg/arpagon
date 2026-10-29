-- Base de données du serveur Arpagon (Cloudflare D1 / SQLite)
-- Création : npx wrangler d1 execute arpagon --remote --file=schema.sql

CREATE TABLE IF NOT EXISTS users (
  id              TEXT PRIMARY KEY,
  email           TEXT NOT NULL UNIQUE,
  created_at      INTEGER NOT NULL,
  stripe_customer TEXT,
  sub_id          TEXT,
  sub_status      TEXT,             -- active, trialing, past_due, canceled, ...
  plan            TEXT,             -- monthly | yearly
  period_end      INTEGER,          -- fin de la période payée (secondes)
  cancel_at_end   INTEGER DEFAULT 0,
  cgv_at          INTEGER           -- date d'acceptation des CGV avant paiement
);
CREATE INDEX IF NOT EXISTS users_customer ON users (stripe_customer);

-- Liens magiques de connexion (on ne garde que l'empreinte du jeton)
CREATE TABLE IF NOT EXISTS login_tokens (
  hash    TEXT PRIMARY KEY,
  email   TEXT NOT NULL,
  expires INTEGER NOT NULL,
  used    INTEGER DEFAULT 0
);

-- Sessions (empreinte du jeton seulement)
CREATE TABLE IF NOT EXISTS sessions (
  hash       TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions (user_id);

-- Sauvegarde chiffrée (AES-GCM) : une par utilisateur
CREATE TABLE IF NOT EXISTS backups (
  user_id    TEXT PRIMARY KEY,
  iv         TEXT NOT NULL,
  data       TEXT NOT NULL,
  size       INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

-- Limitation du nombre de requêtes
CREATE TABLE IF NOT EXISTS rate (
  key   TEXT PRIMARY KEY,
  count INTEGER NOT NULL,
  reset INTEGER NOT NULL
);

-- Webhooks Stripe déjà traités (évite un double traitement)
CREATE TABLE IF NOT EXISTS webhook_events (
  id TEXT PRIMARY KEY,
  at INTEGER NOT NULL
);
