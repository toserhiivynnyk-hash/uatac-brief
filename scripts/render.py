# -*- coding: utf-8 -*-
"""UATAC Sales Brief — рендер дашборду з частин шаблону + analysis.json.
Вихід: /mnt/user-data/outputs/{UATAC_Sales_Brief_<дата>.html, *_drive.html, index.html}
"""
import json, os
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(SKILL_DIR, "templates")
OUT_DIR = os.environ.get("UATAC_OUT", "/mnt/user-data/outputs")
os.makedirs(OUT_DIR, exist_ok=True)

A = json.load(open(OUT_DIR + "/analysis.json"))
data_js = json.dumps(A, ensure_ascii=False, default=str).replace("</", "<\\/")
rd = lambda n: open(os.path.join(TPL, n), encoding="utf-8").read()
head, body, app, chartjs = rd("head.html"), rd("body.html"), rd("app.js"), rd("chartjs.html")

full = (head.replace("__CHARTJS__", chartjs) + body + app).replace("__DATA_JSON__", data_js)
cdn  = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>'
lite = (head.replace("__CHARTJS__", cdn) + body + app).replace("__DATA_JSON__", data_js)

today = A["today"]
for p, c in ((f"{OUT_DIR}/UATAC_Sales_Brief_{today}.html", full),
             (f"{OUT_DIR}/UATAC_Sales_Brief_{today}_drive.html", lite),
             (f"{OUT_DIR}/index.html", full)):
    open(p, "w", encoding="utf-8").write(c)
    print(f"{p}  {round(len(c.encode())/1024)} KB")
