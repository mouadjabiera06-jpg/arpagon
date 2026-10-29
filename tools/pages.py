"""Génère les pages légales et la page de présentation d'Arpagon avec le même gabarit.
Usage : python3 tools/pages.py   (à relancer après chaque modification du texte ci-dessous)

Les infos marquées [À COMPLÉTER] sont à remplir dans IDENT, une seule fois, puis relancer le script.
"""
import os, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IDENT = {
    "nom": "Mouad Jabiera",
    "statut": "Entrepreneur individuel (micro-entreprise)",
    "adresse": "[À COMPLÉTER : adresse postale de domiciliation]",
    "siret": "[À COMPLÉTER : n° SIRET]",
    "email": "[À COMPLÉTER : e-mail de contact]",
    "tva": "TVA non applicable, art. 293 B du CGI",
    "mediateur": "[MÉDIATEUR À CHOISIR : nom, site web et adresse du médiateur auquel tu as adhéré]",
    "maj": "29 octobre 2026",
    "prix_mois": "3,99 €",
    "prix_an": "29,99 €",
}

CSS = """
:root{--bg:#E8DCC6;--card:#FBF5E9;--ink:#3A2B1B;--dim:#6E5A42;--acc:#A8611C;--line:#DCCBAE}
@media (prefers-color-scheme:dark){:root{--bg:#17120C;--card:#221A12;--ink:#F1E6D3;--dim:#B9A588;--acc:#E0A35C;--line:#3A2E21}}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}
a{color:var(--acc);text-underline-offset:2px}
header,main,footer{max-width:760px;margin:0 auto;padding:0 16px}
header{display:flex;align-items:center;gap:10px;padding-top:22px;padding-bottom:6px}
header a{display:flex;align-items:center;gap:10px;color:var(--ink);text-decoration:none;font-weight:700;font-size:20px}
header img{width:34px;height:34px;border-radius:9px}
main{padding-bottom:30px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 22px 10px;margin:16px 0}
h1{font-size:30px;line-height:1.2;margin:18px 0 4px}
h2{font-size:20px;margin:6px 0 10px}
.maj{color:var(--dim);font-size:14px;margin:0}
table{width:100%;border-collapse:collapse;font-size:14.5px;margin:6px 0 14px;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:8px 8px 8px 0;text-align:left;vertical-align:top}
th{font-size:13px;color:var(--dim);font-weight:600}
.todo{background:#f4d58d;color:#3A2B1B;padding:0 4px;border-radius:4px}
footer{border-top:1px solid var(--line);padding-top:16px;padding-bottom:30px;font-size:14px;color:var(--dim)}
footer nav{display:flex;flex-wrap:wrap;gap:6px 16px;margin-bottom:8px}
.btn{display:inline-block;background:var(--acc);color:#fff;text-decoration:none;padding:12px 22px;border-radius:12px;font-weight:700}
.btn.ghost{background:transparent;color:var(--acc);border:1.5px solid var(--acc)}
.hero{text-align:center;padding:30px 0 6px}
.hero h1{font-size:38px;margin-bottom:10px}
.hero p{font-size:19px;color:var(--dim);max-width:560px;margin:0 auto 22px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px}
.grid .card{margin:0}
.plans{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.plans .card{margin:0}
.price{font-size:28px;font-weight:700;margin:2px 0 6px}
ul{padding-left:20px}
"""

FOOT = """<footer>
<nav><a href="presentation.html">Présentation</a><a href="index.html">Ouvrir l'app</a><a href="mentions-legales.html">Mentions légales</a><a href="confidentialite.html">Confidentialité</a><a href="cgv.html">CGV / CGU</a></nav>
Arpagon — {nom}. Aucun cookie publicitaire, aucune mesure d'audience.
</footer>"""


def mark(s):
    """Surligne les champs à compléter pour qu'ils sautent aux yeux."""
    import re
    return re.sub(r"(\[(?:À COMPLÉTER|MÉDIATEUR À CHOISIR)[^\]]*\])", r'<span class="todo">\1</span>', s)


def page(fname, title, desc, body):
    out = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'">
<title>{html.escape(title)} — Arpagon</title>
<meta name="description" content="{html.escape(desc)}">
<meta property="og:title" content="{html.escape(title)} — Arpagon">
<meta property="og:description" content="{html.escape(desc)}">
<link rel="icon" href="logo/arpagon-32.png">
<style>{CSS}</style>
</head>
<body>
<header><a href="presentation.html"><img src="logo/arpagon-192.png" alt="">Arpagon</a></header>
<main>
{mark(body.format(**IDENT))}
</main>
{FOOT.format(**IDENT)}
</body>
</html>
"""
    open(os.path.join(ROOT, fname), "w", encoding="utf-8").write(out)
    print("écrit :", fname)


# ---------------------------------------------------------------- MENTIONS LÉGALES
page("mentions-legales.html", "Mentions légales", "Éditeur, hébergeurs et contact d'Arpagon.", """
<h1>Mentions légales</h1>
<p class="maj">Mise à jour : {maj}</p>
<div class="card">
<h2>Éditeur</h2>
<p>{nom}, {statut}<br>
Adresse : {adresse}<br>
SIRET : {siret}<br>
{tva}<br>
Contact : {email}<br>
Directeur de la publication : {nom}</p>
</div>
<div class="card">
<h2>Hébergement</h2>
<p><b>Application et pages</b> : GitHub Pages — GitHub, Inc., 88 Colin P. Kelly Jr. Street, San Francisco, CA 94107, États-Unis — téléphone : [À COMPLÉTER : vérifier le numéro de GitHub].</p>
<p><b>Serveur Premium (comptes et sauvegardes)</b> : Cloudflare, Inc., 101 Townsend Street, San Francisco, CA 94107, États-Unis — téléphone : [À COMPLÉTER : vérifier le numéro de Cloudflare]. Les données de la base sont stockées dans l'Union européenne.</p>
</div>
<div class="card">
<h2>Propriété intellectuelle</h2>
<p>Le nom Arpagon, le logo, les illustrations et le code de l'application sont la propriété de l'éditeur, sauf mention contraire. Toute reproduction sans autorisation est interdite.</p>
</div>
<div class="card">
<h2>Médiation</h2>
<p>En cas de litige avec un consommateur non résolu à l'amiable, celui-ci peut recourir gratuitement au médiateur de la consommation : {mediateur}.</p>
</div>
""")

# ---------------------------------------------------------------- CONFIDENTIALITÉ
page("confidentialite.html", "Politique de confidentialité", "Quelles données Arpagon traite, pourquoi, combien de temps, et tes droits.", """
<h1>Politique de confidentialité</h1>
<p class="maj">Mise à jour : {maj}</p>
<div class="card">
<h2>L'essentiel</h2>
<ul>
<li><b>Sans compte</b>, tout ce que tu saisis (opérations, budgets, objectifs, dettes, courses) reste <b>uniquement sur ton appareil</b>, dans ton navigateur. L'éditeur n'y a pas accès.</li>
<li><b>Avec un compte Premium</b>, une copie <b>chiffrée</b> de ces données est stockée sur notre serveur pour la synchro entre tes appareils.</li>
<li>Aucune publicité, aucune revente de données, aucun outil de mesure d'audience, aucun cookie publicitaire.</li>
<li>Arpagon ne se connecte à aucune banque : tu notes toi-même tes dépenses.</li>
</ul>
</div>
<div class="card">
<h2>Responsable du traitement</h2>
<p>{nom}, {adresse}. Contact : {email}.</p>
</div>
<div class="card">
<h2>Traitements</h2>
<table>
<tr><th>Données</th><th>Pourquoi</th><th>Base légale</th><th>Durée</th></tr>
<tr><td>Adresse e-mail</td><td>Te connecter (lien magique), gérer ton compte</td><td>Contrat (CGU)</td><td>Jusqu'à la suppression du compte</td></tr>
<tr><td>Sauvegarde de tes données budgétaires (chiffrée)</td><td>Sauvegarde en ligne et synchro entre appareils (Premium)</td><td>Contrat (CGV)</td><td>Jusqu'à la suppression du compte ; effacée immédiatement à la suppression</td></tr>
<tr><td>Statut d'abonnement, identifiants Stripe, date d'acceptation des CGV</td><td>Gérer l'abonnement Premium</td><td>Contrat</td><td>Durée de l'abonnement, puis conservation des pièces comptables 10 ans (obligation légale)</td></tr>
<tr><td>Données de paiement (carte)</td><td>Encaisser l'abonnement</td><td>Contrat</td><td>Traitées et conservées par Stripe uniquement : l'éditeur ne voit jamais ton numéro de carte</td></tr>
<tr><td>Adresse IP, nombre de requêtes</td><td>Sécurité, limiter les abus</td><td>Intérêt légitime</td><td>Compteurs effacés après 1 heure à 24 heures</td></tr>
<tr><td>Jetons de connexion et de session</td><td>Te garder connecté</td><td>Contrat</td><td>15 minutes (lien), 90 jours (session)</td></tr>
</table>
<p>Tes données budgétaires sont chiffrées sur le serveur (AES-256-GCM) et ne sont jamais écrites dans les journaux techniques.</p>
</div>
<div class="card">
<h2>Destinataires et prestataires</h2>
<table>
<tr><th>Prestataire</th><th>Rôle</th><th>Localisation et garanties</th></tr>
<tr><td>Cloudflare, Inc.</td><td>Serveur et base de données Premium</td><td>Base stockée dans l'UE ; société américaine : transferts encadrés [À COMPLÉTER : vérifier Data Privacy Framework ou clauses contractuelles types]</td></tr>
<tr><td>Stripe Payments Europe, Ltd.</td><td>Paiement de l'abonnement</td><td>Irlande (UE)</td></tr>
<tr><td>Resend (Plus Five Five, Inc.)</td><td>Envoi de l'e-mail de connexion</td><td>États-Unis : [À COMPLÉTER : vérifier Data Privacy Framework ou clauses contractuelles types]</td></tr>
<tr><td>GitHub, Inc.</td><td>Hébergement des pages de l'app</td><td>États-Unis : journaux de connexion techniques de GitHub (adresse IP)</td></tr>
</table>
</div>
<div class="card">
<h2>Stockage sur ton appareil (cookies et équivalents)</h2>
<p>Arpagon n'utilise <b>aucun cookie</b>. L'app enregistre dans le stockage local de ton navigateur (localStorage) tes données, tes réglages d'apparence et, si tu es connecté, ton jeton de session. Ce stockage est <b>strictement nécessaire</b> au fonctionnement du service que tu utilises : il ne demande donc pas de consentement. Une copie de l'app est aussi gardée en cache pour fonctionner hors ligne.</p>
<p>Tu peux tout effacer à tout moment en vidant les données du site dans ton navigateur. Pense à exporter ta sauvegarde avant.</p>
</div>
<div class="card">
<h2>Tes droits</h2>
<p>Tu peux demander l'accès, la rectification, l'effacement, la limitation, la portabilité de tes données ou t'opposer à un traitement fondé sur l'intérêt légitime.</p>
<ul>
<li><b>Effacement</b> : Paramètres → Compte &amp; Premium → Supprimer. Compte, sauvegarde et abonnement sont supprimés immédiatement.</li>
<li><b>Portabilité</b> : Paramètres → Données → Exporter la sauvegarde (fichier JSON) ou en CSV.</li>
<li>Pour tout le reste : {email}. Réponse sous un mois.</li>
</ul>
<p>Si tu estimes que tes droits ne sont pas respectés, tu peux saisir la CNIL (<a href="https://www.cnil.fr">cnil.fr</a>).</p>
</div>
""")

# ---------------------------------------------------------------- CGV / CGU
page("cgv.html", "Conditions générales de vente et d'utilisation", "Règles d'utilisation d'Arpagon et conditions de l'abonnement Premium.", """
<h1>Conditions générales de vente et d'utilisation</h1>
<p class="maj">Mise à jour : {maj}</p>
<div class="card">
<h2>1. Objet</h2>
<p>Arpagon est une application web de gestion de budget personnel éditée par {nom} ({statut}, SIRET {siret}, {adresse}, {email}). L'utilisateur y note lui-même ses revenus et dépenses. Arpagon ne se connecte à aucun compte bancaire et ne fournit <b>aucun conseil financier</b> : les chiffres, quêtes et suggestions sont des outils de suivi, pas des recommandations d'investissement.</p>
<p>Ces conditions s'appliquent à toute utilisation d'Arpagon (CGU) et à l'abonnement Premium (CGV). Elles sont acceptées en cochant la case prévue avant tout paiement.</p>
</div>
<div class="card">
<h2>2. Version gratuite</h2>
<p>La version gratuite est utilisable sans compte. Les données sont enregistrées uniquement sur l'appareil de l'utilisateur, qui est seul responsable de leur conservation (export régulier recommandé). L'éditeur ne peut pas récupérer des données effacées d'un appareil.</p>
</div>
<div class="card">
<h2>3. Compte</h2>
<p>Le compte est créé avec une adresse e-mail valide ; la connexion se fait par un lien envoyé à cette adresse, valable 15 minutes et à usage unique. L'utilisateur garde l'accès à sa messagerie confidentiel. Il peut supprimer son compte à tout moment depuis les paramètres de l'app : le compte, la sauvegarde en ligne et l'abonnement éventuel sont alors supprimés.</p>
<p>Il est interdit de tenter de perturber le service, d'accéder aux données d'autrui ou d'automatiser des requêtes abusives. En cas de manquement, l'éditeur peut suspendre le compte après en avoir informé l'utilisateur.</p>
</div>
<div class="card">
<h2>4. Abonnement Premium</h2>
<p><b>Contenu</b> : sauvegarde en ligne chiffrée des données et synchronisation automatique entre les appareils de l'utilisateur.</p>
<p><b>Prix</b> : {prix_mois} par mois ou {prix_an} par an, prix TTC ({tva}). Les prix applicables sont ceux affichés au moment de la souscription.</p>
<p><b>Paiement</b> : par carte bancaire, via Stripe, au début de chaque période. L'abonnement est reconduit automatiquement pour la même durée jusqu'à résiliation.</p>
<p><b>Résiliation</b> : à tout moment, en ligne, depuis Paramètres → Compte &amp; Premium → « Gérer ou résilier mon abonnement ». La résiliation prend effet à la fin de la période déjà payée ; aucun remboursement au prorata n'est dû hors droit de rétractation. Sans abonnement actif, la sauvegarde en ligne n'est plus accessible ; les données restent sur les appareils de l'utilisateur.</p>
<p><b>Défaut de paiement</b> : si un paiement échoue, Stripe réessaie pendant quelques jours ; sans régularisation, l'abonnement prend fin.</p>
</div>
<div class="card">
<h2>5. Droit de rétractation</h2>
<p>Le consommateur dispose de <b>14 jours</b> à compter de la souscription pour se rétracter, sans motif, en écrivant à {email} (le formulaire ci-dessous peut être utilisé). En demandant que le service commence dès le paiement, il accepte, s'il se rétracte, de payer la part du prix correspondant à la période déjà écoulée ; le reste est remboursé sous 14 jours par le même moyen de paiement.</p>
</div>
<div class="card">
<h2>6. Garanties et responsabilité</h2>
<p>Le service bénéficie de la garantie légale de conformité applicable aux services numériques (articles L224-25-12 et suivants du Code de la consommation). L'éditeur fait ses meilleurs efforts pour assurer la disponibilité du service mais ne garantit pas une absence totale d'interruption (maintenance, panne d'un prestataire). Sa responsabilité ne saurait être engagée pour une décision financière prise par l'utilisateur sur la base des informations qu'il a lui-même saisies.</p>
</div>
<div class="card">
<h2>7. Données personnelles</h2>
<p>Voir la <a href="confidentialite.html">politique de confidentialité</a>.</p>
</div>
<div class="card">
<h2>8. Modification des conditions</h2>
<p>L'éditeur peut modifier ces conditions. Les abonnés sont prévenus par e-mail au moins 30 jours avant toute modification qui les concerne et peuvent résilier sans frais avant son entrée en vigueur.</p>
</div>
<div class="card">
<h2>9. Réclamations, médiation et droit applicable</h2>
<p>Toute réclamation est à adresser à {email}. À défaut de solution amiable, le consommateur peut saisir gratuitement le médiateur de la consommation : {mediateur}. Ces conditions sont soumises au droit français ; le consommateur conserve la protection des règles impératives de son pays de résidence.</p>
</div>
<div class="card">
<h2>Annexe — formulaire de rétractation</h2>
<p>À l'attention de {nom}, {adresse}, {email} :<br>
Je notifie par la présente ma rétractation du contrat portant sur l'abonnement Arpagon Premium.<br>
Souscrit le : …………<br>
Nom : …………<br>
Adresse e-mail du compte : …………<br>
Date : …………</p>
</div>
""")

# ---------------------------------------------------------------- PRÉSENTATION
page("presentation.html", "Reprends la main sur ton argent", "Arpagon, l'app de budget où tu notes toi-même chaque dépense pour en prendre conscience. Gratuite, sans pub, sans connexion bancaire.", """
<section class="hero">
<h1>Note tes dépenses.<br>Prends-en conscience.</h1>
<p>Arpagon est une app de budget qui ne se connecte pas à ta banque, exprès : c'est en notant chaque dépense toi-même que tu reprends la main. Et pour tenir dans la durée, ça se joue comme une quête.</p>
<p><a class="btn" href="index.html">Ouvrir Arpagon — gratuit</a></p>
</section>
<div class="grid">
<div class="card"><h2>Quêtes et niveaux</h2><p>Des missions chaque mois, de l'XP, un compagnon qui réagit à ta discipline.</p></div>
<div class="card"><h2>Budgets par enveloppe</h2><p>Une limite par catégorie, les charges fixes notées une fois pour toutes.</p></div>
<div class="card"><h2>Courses</h2><p>Ta liste de la semaine, un sac qui se remplit avec tes tickets et déborde si tu dépasses.</p></div>
<div class="card"><h2>Objectifs et dettes</h2><p>Épargne pour tes projets, suivi de ce que tu dois et de ce qu'on te doit.</p></div>
</div>
<h2 style="margin-top:28px">Deux formules</h2>
<div class="plans">
<div class="card"><h2>Gratuit</h2><div class="price">0 €</div><ul><li>Toute l'app, sans limite</li><li>Données sur ton appareil uniquement</li><li>Fonctionne hors ligne</li><li>Export JSON et CSV</li></ul></div>
<div class="card"><h2>Premium <span style="font-size:14px;font-weight:400;color:var(--dim)">— bientôt disponible</span></h2><div class="price">{prix_mois}<span style="font-size:15px;font-weight:400"> / mois</span></div><p style="margin-top:0">ou {prix_an} / an</p><ul><li>Sauvegarde en ligne chiffrée</li><li>Synchro téléphone ↔ ordinateur</li><li>Sans engagement, résiliable en ligne</li></ul></div>
</div>
<div class="card">
<h2>Tes données</h2>
<p>Pas de pub, pas de revente, pas de mesure d'audience. Sans compte, rien ne quitte ton appareil. Avec Premium, ta sauvegarde est chiffrée. <a href="confidentialite.html">En savoir plus</a></p>
</div>
<p style="text-align:center;margin-top:24px"><a class="btn" href="index.html">Commencer maintenant</a></p>
""")
