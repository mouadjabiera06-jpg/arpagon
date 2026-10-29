# Arpagon

App de budget personnel où l'on **note soi-même chaque dépense** pour en prendre conscience. Pas de connexion bancaire, exprès. Quêtes, niveaux et compagnon pour tenir dans la durée.

- **Gratuit** : toute l'app, données uniquement dans le navigateur, fonctionne hors ligne, export JSON/CSV.
- **Arpagon+ (1,99 €/mois ou 14,99 €/an, 14 jours offerts ; 0,99 €/mois ou 9,99 €/an pour les 100 premiers)** : sauvegarde en ligne chiffrée, synchro entre appareils, thèmes exclusifs, bilan annuel complet, tendances 12 mois.

App : https://mouadjabiera06-jpg.github.io/arpagon/ · Présentation : `presentation.html`

## Contenu du dépôt

| Fichier | Rôle |
| --- | --- |
| `index.html` | L'app (un seul fichier HTML/CSS/JS) |
| `sw.js` | Service worker : l'app s'ouvre sans réseau |
| `manifest.json`, `logo/` | Installation sur l'écran d'accueil |
| `arpagon-pc.html` | Lanceur PC perso (charge la dernière version depuis GitHub) |
| `presentation.html` | Page de présentation |
| `mentions-legales.html`, `confidentialite.html`, `cgv.html` | Pages légales, générées par `tools/pages.py` |
| `server/` | Serveur Premium (Cloudflare Worker + base D1) |
| `tests/` | Tests du serveur (`npm test`) et de l'app (`tests/app_test.py`) |

## Règles de travail

- On travaille sur la branche **`dev`**. `main` = ce que voient les utilisateurs : on n'y fusionne qu'après test.
- Avant chaque fusion : `npm test` (serveur) et `python3 tests/app_test.py` (app, nécessite Playwright).
- Pages légales : modifier le texte ou les infos dans `tools/pages.py`, puis `python3 tools/pages.py`. Ne pas éditer les `.html` générés à la main.

## Mise en ligne du Premium (une seule fois)

Prérequis : Node.js installé sur ton PC, un compte Cloudflare, un compte Stripe, un compte Resend, un nom de domaine.

### 1. Base de données et serveur

```bash
cd server
npx wrangler login
npx wrangler d1 create arpagon --jurisdiction eu      # données stockées dans l'UE
# → copie le "database_id" affiché dans wrangler.toml
npx wrangler d1 execute arpagon --remote --file=schema.sql
```

### 2. Stripe (d'abord en mode test)

1. Produits → créer **Arpagon+** avec quatre prix récurrents : 1,99 €/mois, 14,99 €/an, et les prix fondateur 0,99 €/mois et 9,99 €/an. Copier les quatre `price_…` dans `wrangler.toml` (laisser les prix fondateur vides pour désactiver l'offre).
2. Paramètres → Portail client : autoriser la résiliation et la mise à jour de la carte.
3. Après le déploiement (étape 4) : Développeurs → Webhooks → ajouter `https://<ton-worker>/stripe/webhook` avec les événements `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`. Copier le secret `whsec_…`.

### 3. E-mails (Resend)

Ajouter ton domaine dans Resend, créer les enregistrements DNS demandés, puis mettre `MAIL_FROM = "Arpagon <connexion@ton-domaine.fr>"` dans `wrangler.toml`.

### 4. Secrets et déploiement

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"   # → DATA_KEY
npx wrangler secret put DATA_KEY
npx wrangler secret put STRIPE_SECRET            # sk_test_… puis sk_live_… au lancement
npx wrangler secret put STRIPE_WEBHOOK_SECRET    # whsec_…
npx wrangler secret put RESEND_KEY
npx wrangler deploy
```

⚠️ **Garde `DATA_KEY` en lieu sûr (gestionnaire de mots de passe).** Si elle est perdue ou changée, toutes les sauvegardes en ligne deviennent illisibles.

### 5. Brancher l'app

Dans `index.html`, renseigner l'adresse affichée par `wrangler deploy` :

```js
var API = "https://arpagon-api.TONCOMPTE.workers.dev";
```

Si tu passes sur ton propre domaine, ajoute-le à `APP_ORIGINS` et `APP_URL` (wrangler.toml) et à `connect-src` dans la balise Content-Security-Policy de `index.html`.

### 6. Tester en mode test, puis passer en réel

Carte de test Stripe : `4242 4242 4242 4242`, date future, n'importe quel code. Vérifier : connexion par e-mail, paiement, Premium actif, synchro sur un 2e appareil, résiliation depuis le portail, suppression du compte. Ensuite seulement : clés `sk_live_…`, nouveau webhook en mode réel, nouveaux `price_…` réels.
