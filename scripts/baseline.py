# -*- coding: utf-8 -*-
"""UATAC — база порівняння «рік до року».
Тягне довге вікно з KeyCRM (за замовчуванням 540 днів) і зводить його у компактний
baseline.json: денні факти по групах каналів + місячні підсумки.
Запускати раз на тиждень — щоденному брифу вистачає кешу.
Запуск: python3 scripts/baseline.py [--days 540]
"""
import json, datetime, os, sys, subprocess
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("UATAC_BASELINE", "baseline.json")
RAW = os.environ.get("UATAC_BASELINE_RAW", ".cache/keycrm_long.json")
DAYS = 540
if "--days" in sys.argv: DAYS = int(sys.argv[sys.argv.index("--days") + 1])

if not os.path.exists(RAW) or "--refetch" in sys.argv:
    env = dict(os.environ, UATAC_RAW=RAW)
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "fetch.py"), "--days", str(DAYS)], env=env)
    if r.returncode: sys.exit(r.returncode)

RAWD = json.load(open(RAW))
STATUS = {s["id"]: s for s in RAWD["statuses"]}
SOURCES = {s["id"]: s["name"] for s in RAWD.get("sources", [])}
USD_UAH = 46
B2B_HINTS = ("Дроп", "Дилер", "Гайдамак", "Епіцентр", "MURAVEINYK", "Піксель", "Military Sector",
             "ПЛЮС+ПЛЮС", "ШТУРМ", "ЗАПОРІЖЖЯ", "Happy GO", "U-ARM", "Козаків", "Prom", "Rozetka", "Списання")
GROUPS = ["site_ua", "b2b", "intl", "bot", "manual", "social_leads", "other"]

def group_of(o):
    sid = o.get("source_id"); nm = SOURCES.get(sid, "")
    if sid == 37: return "intl"
    if sid == 69: return "bot"
    if any(h in nm for h in B2B_HINTS): return "b2b"
    if sid in (5, 18, 28, 57, 61, 10): return "manual"
    if sid in (6, 63, 7, 49, 11): return "social_leads"
    if sid == 1: return "site_ua"
    return "other"

start = datetime.date.fromisoformat(RAWD["period_start"])
end = datetime.date.fromisoformat(RAWD["period_end"])
DATES = [str(start + datetime.timedelta(days=i)) for i in range((end - start).days + 1)]
DI = {d: i for i, d in enumerate(DATES)}
GI = {g: i for i, g in enumerate(GROUPS)}

bucket = defaultdict(lambda: [0, 0.0, 0.0, 0])   # orders, revenue, margin, cancelled
months = defaultdict(lambda: {"revenue": 0.0, "orders": 0, "margin": 0.0, "cancelled": 0, "items": 0})
for o in RAWD["orders"]:
    gid = STATUS.get(o.get("status_id"), {}).get("group_id")
    cl = o.get("closed_at")
    if gid not in (5, 6) or not cl: continue
    try: d = datetime.datetime.fromisoformat(cl.replace("Z", "+00:00")).date()
    except Exception: continue
    di = DI.get(str(d))
    if di is None: continue
    g = group_of(o); fx = USD_UAH if g == "intl" else 1
    mk = f"{d.year}-{d.month:02d}"
    k = (di, GI[g])
    if gid == 6:
        bucket[k][3] += 1; months[mk]["cancelled"] += 1; continue
    rev = (o.get("grand_total") or 0) * fx
    mar = (o.get("margin_sum") or 0) * fx
    bucket[k][0] += 1; bucket[k][1] += rev; bucket[k][2] += mar
    months[mk]["revenue"] += rev; months[mk]["orders"] += 1; months[mk]["margin"] += mar
    months[mk]["items"] += sum(p.get("quantity") or 1 for p in (o.get("products") or []))

for m in months.values():
    m["revenue"] = round(m["revenue"]); m["margin"] = round(m["margin"])
    m["aov"] = round(m["revenue"] / m["orders"]) if m["orders"] else 0
    m["items_per_order"] = round(m["items"] / m["orders"], 2) if m["orders"] else 0
    m["margin_pct"] = round(m["margin"] / m["revenue"] * 100) if m["revenue"] else 0
    m["cancel_pct"] = round(m["cancelled"] / (m["orders"] + m["cancelled"]) * 100) if (m["orders"] + m["cancelled"]) else 0

OUTD = {
    "built_at": datetime.datetime.now().isoformat(timespec="seconds"),
    "from": str(start), "to": str(end),
    "dates": DATES, "groups": GROUPS,
    "facts": [[k[0], k[1], v[0], round(v[1]), round(v[2]), v[3]] for k, v in sorted(bucket.items())],
    "months": dict(sorted(months.items())),
}
json.dump(OUTD, open(OUT, "w"), ensure_ascii=False)
print(f"baseline → {OUT}: {len(DATES)} днів, {len(OUTD['facts'])} фактів, {len(months)} місяців "
      f"({round(os.path.getsize(OUT)/1024)} KB)")
mk = sorted(months)[-14:]
for m in mk:
    v = months[m]
    ly = months.get(f"{int(m[:4])-1}{m[4:]}")
    d = f"{(v['revenue']-ly['revenue'])/ly['revenue']*100:+.0f}% YoY" if ly and ly["revenue"] else "—"
    print(f"  {m}  {v['revenue']:>9} ₴  {v['orders']:>4} зам  AOV {v['aov']:>6}  {d}")
