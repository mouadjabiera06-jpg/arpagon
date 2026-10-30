"""Tests du thème perso et du fond d'écran réservés à Arpagon+ : python3 tests/theme_test.py"""
import json, os, tempfile, threading, http.server, socketserver
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8767
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
    pg.reload(); pg.wait_for_timeout(800)
    E = pg.evaluate
    root = "getComputedStyle(document.documentElement).getPropertyValue('{}').trim()"

    # --- Sans Arpagon+ ---
    E("() => { LS.del(PREM_KEY); AP.theme = 'perso'; saveAppearance(); }")
    check("gratuit : le thème perso retombe sur le thème par défaut", E("AP.theme") == E("AP_DEF.theme"))
    E("App.setTheme('perso')")
    check("gratuit : choisir le thème perso est refusé", E("AP.theme") != "perso")
    E("App.setCustom('bg', '#000000', 1)")
    check("gratuit : modifier une couleur est refusé", E("AP.theme") != "perso")
    E("App.go('set')"); pg.wait_for_timeout(300)
    html = E("document.getElementById('app') ? document.getElementById('app').innerHTML : document.body.innerHTML")
    check("gratuit : panneau thème perso verrouillé", "Crée ton propre thème" in html and E("document.querySelectorAll('.cpk input').length") == 0)
    check("gratuit : pas de bouton pour choisir un fond d'écran", E("document.querySelectorAll('[onclick*=pickWP]').length") == 0 and "propre image en fond" in html)
    E("() => { WP = 'data:image/png;base64,iVBORw0KGgo='; applyAppearance(); }")
    check("gratuit : un ancien fond d'écran n'est pas affiché", not E("document.documentElement.classList.contains('wp')"))

    # --- Avec Arpagon+ ---
    E("() => { LS.set(PREM_KEY, '1'); }")
    E("App.setTheme('perso')")
    check("plus : le thème perso s'applique", E("AP.theme") == "perso")
    check("plus : fond d'écran affiché", E("document.documentElement.classList.contains('wp')"))
    E("() => { WP = ''; applyAppearance(); }")
    E("App.setCustom('bg', '#102030', 1)"); E("App.setCustom('acc', '#FF8800', 1)")
    check("plus : la couleur de fond suit le choix", E(root.format("--s-bg")).lower() == "#102030")
    check("plus : l'accent suit le choix", E(root.format("--ind")).lower() == "#ff8800")
    check("plus : fond sombre => base sombre", E("document.documentElement.getAttribute('data-theme')") == "nuit")
    E("App.setCustom('bg', '#F7F3EE', 1)")
    check("plus : fond clair => base claire", E("document.documentElement.getAttribute('data-theme')") == "clair")
    E("App.setCustom('acc', 'rouge', 1)")
    check("couleur invalide ignorée", E("AP.custom.acc").lower() == "#ff8800")
    E("App.go('set')"); pg.wait_for_timeout(300)
    check("plus : 4 sélecteurs de couleur", E("document.querySelectorAll('.cpk input[type=color]').length") == 4)

    # export / import
    exp = json.loads(E("themeFile()"))
    check("export : fichier thème complet", exp["arpagonTheme"] == 1 and exp["bg"].lower() == "#f7f3ee" and exp["acc"].lower() == "#ff8800")
    good = {"arpagonTheme": 1, "name": "Lagon", "bg": "#062A33", "card": "#0B3A45", "txt": "#E6FAFF", "acc": "#22D3EE"}
    d = tempfile.mkdtemp()
    for nm, data in [("ok.json", json.dumps(good)), ("ko.json", '{"bg":"#000"}'), ("pas-json.json", "coucou")]:
        open(os.path.join(d, nm), "w").write(data)
    E("App.setTheme('taverne')")
    pg.set_input_files("#thIn", os.path.join(d, "ok.json")); pg.wait_for_timeout(400)
    check("import : thème appliqué", E("AP.theme") == "perso" and E("AP.custom.name") == "Lagon" and E(root.format("--s-bg")).lower() == "#062a33")
    for nm in ["ko.json", "pas-json.json"]:
        pg.set_input_files("#thIn", os.path.join(d, nm)); pg.wait_for_timeout(300)
        check("import refusé : " + nm, E("AP.custom.name") == "Lagon")

    # quitter le thème perso efface les couleurs perso
    E("App.setTheme('taverne')")
    check("retour à un thème normal : couleurs perso retirées", E("document.documentElement.style.getPropertyValue('--s-bg')") == "")

    # anneau de discipline aux couleurs du thème
    E("App.setTheme('royal')"); E("App.go('dash')"); pg.wait_for_timeout(300)
    E("() => { var real = discipline; window.discipline = function (m) { var d = real(m); d.score = 90; return d; }; render(); }")
    pg.wait_for_timeout(300)
    stroke = E("document.querySelectorAll('.ring circle')[1].getAttribute('stroke')")
    check("bon score : anneau à la couleur du thème", stroke == "var(--ind)")

    check("aucune erreur JS", not errors)
    if errors: print(errors)
    b.close()

srv.shutdown()
print("\nTOUT EST OK" if not fails else "\n%d ÉCHEC(S)" % len(fails))
raise SystemExit(1 if fails else 0)
