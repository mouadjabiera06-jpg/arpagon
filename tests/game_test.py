"""Tests du jeu (série, joker, quêtes, badges, tenues) : python3 tests/game_test.py"""
import json, os, sys, threading, http.server, socketserver
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8766
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", PORT), Q)
threading.Thread(target=srv.serve_forever, daemon=True).start()

fails, errors = [], []
def check(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"http://127.0.0.1:{PORT}/index.html")
    pg.evaluate("localStorage.setItem('budgetv2:data', JSON.stringify(Object.assign({}, DEF, {settings: Object.assign({}, DEF.settings, {onboard: false})})))")
    pg.reload(); pg.wait_for_timeout(1000)
    E = pg.evaluate

    # --- Série et joker ---
    E("""() => { var t = todayISO(); S.game.days = {};
      [1,2,3,4,5].forEach(function (i) { S.game.days[isoShift(t, -i)] = 1; }); }""")
    s = E("streak()"); check("série de 5 jours, aujourd'hui pas encore noté", s["n"] == 5 and not s["today"])
    E("() => { var t = todayISO(); S.game.days = {}; [0,1,3,4].forEach(function (i) { S.game.days[isoShift(t, -i)] = 1; }); }")
    s = E("streak()"); check("un trou pardonné par le joker (4 jours, joker utilisé)", s["n"] == 4 and not s["joker"])
    E("() => { var t = todayISO(); S.game.days = {}; [0,1,3,4,6,7].forEach(function (i) { S.game.days[isoShift(t, -i)] = 1; }); }")
    s = E("streak()"); check("deux trous dans la même semaine : la série casse", s["n"] == 4)
    E("() => { var t = todayISO(); S.game.days = {}; [0,1,2,4].forEach(function (i) { S.game.days[isoShift(t, -i)] = 1; }); }")
    check("pas de double comptage aujourd'hui", E("markToday()") is False)

    # --- Récompense quotidienne ---
    E("() => { S.game.days = {}; S.game.xp = 0; S.game.claimed = {}; }")
    E("dailyReward()"); x1 = E("S.game.xp"); E("dailyReward()"); x2 = E("S.game.xp")
    check("+5 XP la première saisie du jour, pas la suivante", x1 == 5 and x2 == 5)
    E("() => { var t = todayISO(); S.game.days = {}; S.game.claimed = {}; S.game.xp = 0; [1,2,3,4,5,6].forEach(function (i) { S.game.days[isoShift(t, -i)] = 1; }); }")
    E("dailyReward()")
    check("palier 7 jours : +25 XP de bonus", E("S.game.xp") == 30 and E("!!S.game.claimed['s:7']"))

    # --- Bug : dates futures ---
    E("""() => { var m = curMonth(); S.transactions = [];
      for (var d = 1; d <= daysIn(m); d++) S.transactions.push({ id: 'f' + d, type: 'expense', amount: 1, categoryId: 'divers', date: m + '-' + pad(d) }); }""")
    ad = E("activeDays(curMonth())"); today = E("+todayISO().slice(8)")
    check("les jours futurs ne comptent pas", ad == today)

    # --- Bug : 20 points offerts sans tri ---
    E("""() => { var m = curMonth(); S.transactions = [{ id: 'i', type: 'income', amount: 1000, categoryId: 'salaire', date: m + '-01' }];
      for (var i = 0; i < 10; i++) S.transactions.push({ id: 'e' + i, type: 'expense', amount: 10, categoryId: 'divers', date: m + '-01', useful: null }); }""")
    p4 = E("discipline(curMonth()).parts[3].v")
    check("aucun achat trié = 0 point en dépenses réfléchies", p4 == 0)
    E("() => S.transactions.forEach(function (t) { if (t.type === 'expense') t.useful = 'useful'; })")
    check("tout trié, rien d'inutile = 20 points", round(E("discipline(curMonth()).parts[3].v")) == 20)

    # --- Bug : quête épargne payée deux fois ---
    E("() => { S.game.claimed = {}; S.game.claimed[curMonth() + ':save5'] = 1; }")
    sq = E("missionsFor(curMonth()).filter(function (x) { return x.id === 'save'; })[0]")
    check("ancienne quête épargne déjà payée = pas repayée", sq is None or sq["done"])

    # --- Bug : mois sauté ---
    E("""() => { var cur = curMonth(), m2 = shiftM(cur, -2); S.game.claimed = {}; S.game.xp = 0;
      S.game.settled = shiftM(cur, -3);
      S.transactions = [];
      for (var d = 1; d <= 6; d++) S.transactions.push({ id: 'x' + d, type: 'expense', amount: 2, categoryId: 'divers', date: m2 + '-0' + d }); }""")
    g = E("settleMonths()")
    check("quêtes d'un mois sauté soldées quand même", g["gained"] > 0 and any(k.startswith(E("shiftM(curMonth(), -2)")) for k in E("Object.keys(S.game.claimed)")))
    check("rien de payé deux fois au 2e passage", E("settleMonths().gained") == 0)

    # --- Badges ---
    E("() => { S.game.badges = {}; S.game.best = 7; rewQ = []; }")
    E("checkBadges()")
    got = E("Object.keys(S.game.badges)")
    check("badges Premier pas + 7 jours débloqués", "premier" in got and "serie7" in got)
    n = E("Object.keys(S.game.badges).length"); E("checkBadges()")
    check("un badge ne se gagne qu'une fois", E("Object.keys(S.game.badges).length") == n)

    # --- Tenues ---
    E("() => { S.game.xp = 0; S.game.wear = []; }")
    E("App.toggleWear('couronne')")
    check("tenue verrouillée refusée", E("S.game.wear.length") == 0)
    E("() => { var b = levelOf(S.game.xp).lvl.n; S.game.xp = 700; rewQ = []; levelUps(b); }")
    check("niveaux 2 à 4 franchis d'un coup : 3 tenues portées", sorted(E("S.game.wear")) == ["echarpe", "lunettes", "piece"])
    check("le compagnon affiche la tenue", "C8463D" in E("mascotSvg('taverne', 80, 'f')"))
    norm = E("normalize({ game: { xp: 5000, claimed: {} } }).game.wear.length")
    check("ancienne sauvegarde niveau 9 : 8 tenues mises d'office", norm == 8)

    # --- Rendu ---
    E("() => { S.game.wear = ['echarpe','lunettes','piece','cape','sacoche','medaille','laurier','aura','couronne']; S.game.xp = 7000; save(); App.go('dash'); }")
    pg.wait_for_timeout(500)
    check("bandeau de série sur l'accueil", E("!!document.querySelector('.streak')"))
    E("App.openProgress()"); pg.wait_for_timeout(300)
    check("badges dans la progression", E("document.querySelectorAll('.bdg').length") == 13)

check("aucune erreur JS", not errors)
for e in errors: print("  ", e)
print("\n" + ("TOUT EST OK" if not fails and not errors else str(len(fails)) + " échec(s)"))
sys.exit(1 if fails or errors else 0)
