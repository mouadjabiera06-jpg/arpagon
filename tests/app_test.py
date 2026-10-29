"""Test de l app dans un vrai navigateur (Playwright) : python3 tests/app_test.py"""
import json, os, sys, threading, http.server, socketserver, functools
from playwright.sync_api import sync_playwright

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8765
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", PORT), Q)
threading.Thread(target=srv.serve_forever, daemon=True).start()

XSS = '<img src=x onerror="window.__xss=(window.__xss||0)+1">'
seed = {
  "version": 4,
  "transactions": [
    {"id": "a1", "type": "expense", "amount": 12.5, "categoryId": "courses", "date": "2026-10-03", "payMethod": "Carte", "note": XSS, "useful": "useful"},
    {"id": "a2", "type": "income", "amount": 900, "categoryId": "salaire", "date": "2026-10-01", "note": "Salaire"},
    {"id": "a3", "type": "expense", "amount": 50, "categoryId": "epargne", "date": "2026-10-05", "note": "Livret A"},
  ],
  "fixed": [], "budgets": [{"month": "2026-10", "categoryId": "courses", "amount": 150}],
  "goals": [{"id": "g1", "name": XSS, "target": 500, "saved": 20}],
  "wishlist": [{"id": "w1", "name": XSS, "price": 40, "prio": 1}],
  "debts": [{"id": "d1", "name": XSS, "kind": "owed", "total": 100, "remaining": 60, "monthly": 10}],
  "shop": {"items": [{"id": "s1", "name": XSS, "qty": 1, "price": 2, "freq": "week", "kind": "food"}], "limit": 120},
  "settings": {"currency": "€", "monthlyGoal": 100, "alertThreshold": 50, "onboard": False},
}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.on("pageerror", lambda e: errors.append("PAGEERROR " + str(e)))
    pg.on("console", lambda m: m.type == "error" and errors.append("CONSOLE " + m.text))
    pg.goto(f"http://127.0.0.1:{PORT}/index.html")
    pg.evaluate("s => localStorage.setItem('budgetv2:data', s)", json.dumps(seed))
    pg.reload(); pg.wait_for_timeout(1500)
    for t in ["dash", "tx", "shop", "bud", "goal", "debt", "stat", "hist", "set"]:
        try:
            pg.evaluate(f"App.go('{t}')"); pg.wait_for_timeout(300)
        except Exception as e:
            errors.append(f"TAB {t}: {e}")
    pg.evaluate("App.setGoalSub && App.setGoalSub('wish')"); pg.wait_for_timeout(200)
    for f in ["newTx()", "newGoal()", "newWish()", "newDebt()", "newShop()", "openPal()", "openProgress()", "more()"]:
        try:
            pg.evaluate(f"App.{f}"); pg.wait_for_timeout(250); pg.evaluate("App.closeSheet(true); App.closePal()")
        except Exception as e:
            errors.append(f"ACTION {f}: {e}")
    print("XSS fired:", pg.evaluate("window.__xss||0"))
    # toast injection
    pg.evaluate("toast('<img src=x onerror=\"window.__t=1\">')"); pg.wait_for_timeout(400)
    print("toast HTML injection:", pg.evaluate("window.__t||0"))
    # CSV with 1.234,56 format and duplicate re-import
    n0 = pg.evaluate("S.transactions.length")
    csv = "Date;Libellé;Montant\n05/10/2026;LOYER CROUS;-1.234,56\n06/10/2026;\"CAFE; ROND\";-3,20\n07/10/2026;CARREFOUR;\"-1 012,40\"\n08/10/2026;VIR LIVRET A;-50,00\n"
    print("import1", pg.evaluate("c => importCSV(c)", csv)); print("import2", pg.evaluate("c => importCSV(c)", csv))
    amts = pg.evaluate("S.transactions.slice(-4).map(t=>t.amount+' '+t.categoryId+' '+t.note)")
    print("CSV import x2 (expect 4 added once):", pg.evaluate("S.transactions.length") - n0, amts)
    # restore an old backup without game
    old = {k: v for k, v in seed.items()}
    pg.evaluate("d => { var x = JSON.parse(d); S = Object.assign({}, DEF, x); S.settings = Object.assign({}, DEF.settings, x.settings||{}); delete S.game; render(); }", json.dumps(old))
    pg.wait_for_timeout(500)
    # scroll listener wiring before any keypress
    pg2 = b.new_page()
    pg2.add_init_script("""
      (function(){ var o = EventTarget.prototype.addEventListener; window.__scroll=0;
        EventTarget.prototype.addEventListener = function(t, f, op){ if (t==='scroll') window.__scroll++; return o.call(this,t,f,op); }; })();
    """)
    pg2.goto(f"http://127.0.0.1:{PORT}/index.html"); pg2.wait_for_timeout(1200)
    before = pg2.evaluate("window.__scroll")
    pg2.keyboard.press("Shift"); pg2.keyboard.press("Shift")
    print("scroll listeners: before key =", before, "after 2 keys =", pg2.evaluate("window.__scroll"))
    # mobile view
    pm = b.new_page(viewport={"width": 375, "height": 780})
    pm.on("pageerror", lambda e: errors.append("MOBILE " + str(e)))
    pm.goto(f"http://127.0.0.1:{PORT}/index.html"); pm.wait_for_timeout(1000)
    sw = pm.evaluate("document.documentElement.scrollWidth")
    print("mobile scrollWidth:", sw)
    print("service worker registered:", pg.evaluate("!!(navigator.serviceWorker && navigator.serviceWorker.controller)"))
    b.close()
print("ERRORS:", len(errors))
for e in errors[:40]: print(" -", e[:300])
srv.shutdown()
