# -*- coding: utf-8 -*-
"""UATAC Sales Brief — аналітичний движок v2 (period-aware, drill-down ready).
Вхід: /home/claude/keycrm_raw.json (з fetch.py). Вихід: /mnt/user-data/outputs/analysis.json
База: ТІЛЬКИ закриті угоди (closed_at, status_group_id==5). group 6 = скасовані.
Групи 1-4 = «В роботі» (pipeline) — випереджальний індикатор.
"""
import json, datetime, calendar, re, os, sys
from collections import defaultdict, Counter

RAW_PATH = os.environ.get("UATAC_RAW", "/home/claude/keycrm_raw.json")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYBOOK = os.environ.get("UATAC_PLAYBOOK") or os.path.join(SKILL_DIR, "playbook.json")
BASELINE = os.environ.get("UATAC_BASELINE", "baseline.json")
SPEND    = os.environ.get("UATAC_SPEND", "spend.json")
# Ціль місяця: число або None → береться повна виручка минулого місяця
MONTH_TARGET = float(os.environ.get("UATAC_MONTH_TARGET") or 0) or None
DEC_PATH = os.environ.get("UATAC_DECISIONS", "/home/claude/decisions.json")
OUT_DIR = os.environ.get("UATAC_OUT", "/mnt/user-data/outputs")
os.makedirs(OUT_DIR, exist_ok=True)

RAW = json.load(open(RAW_PATH))
TODAY = datetime.date.fromisoformat(RAW["period_end"])
DATA_START = datetime.date.fromisoformat(RAW["period_start"])
MON_START = TODAY.replace(day=1)
prev_last = MON_START - datetime.timedelta(days=1)
PREV_START = prev_last.replace(day=1)
PREV_SAME_END = PREV_START + datetime.timedelta(days=min(TODAY.day, prev_last.day) - 1)
D14 = TODAY - datetime.timedelta(days=14)
DAYS_IN_MON = calendar.monthrange(TODAY.year, TODAY.month)[1]
REM_DAYS = DAYS_IN_MON - TODAY.day
UA_MON = {1:"січень",2:"лютий",3:"березень",4:"квітень",5:"травень",6:"червень",
          7:"липень",8:"серпень",9:"вересень",10:"жовтень",11:"листопад",12:"грудень"}
UA_MON_GEN = {1:"січня",2:"лютого",3:"березня",4:"квітня",5:"травня",6:"червня",
              7:"липня",8:"серпня",9:"вересня",10:"жовтня",11:"листопада",12:"грудня"}
UA_MON3 = {1:"Січ",2:"Лют",3:"Бер",4:"Кві",5:"Тра",6:"Чер",7:"Лип",8:"Сер",9:"Вер",10:"Жов",11:"Лис",12:"Гру"}
USD_UAH = 46
DONE_GROUP, CANCEL_GROUP = 5, 6

def fmt_int(n): return f"{round(n):,}".replace(",", " ")

STATUS = {s["id"]: s for s in RAW["statuses"]}
SOURCES = {s["id"]: s["name"] for s in RAW.get("sources", [])}

B2B_HINTS = ("Дроп", "Дилер", "Гайдамак", "Епіцентр", "MURAVEINYK", "Піксель",
             "Military Sector", "ПЛЮС+ПЛЮС", "ШТУРМ", "ЗАПОРІЖЖЯ", "Happy GO",
             "U-ARM", "Козаків", "Prom", "Rozetka", "Списання")

def classify(o):
    sid = o.get("source_id")
    sname = SOURCES.get(sid, f"src_{sid}")
    m = o.get("marketing") or {}
    us = (m.get("utm_source") or "").strip().lower()
    um = (m.get("utm_medium") or "").strip().lower()
    if sid == 37: return "intl", "Shopify INTL"
    if sid == 69: return "bot", "Леся (AI-бот)"
    if any(h in sname for h in B2B_HINTS): return "b2b", "B2B: дропи/дилери/маркетплейси"
    if sid in (5, 18, 28, 57, 61, 10): return "manual", "Офіс / телефон (ручні)"
    if sid in (6, 63): return "social_leads", "Lead-форми FB/TikTok"
    if sid in (7, 49, 11): return "social_leads", "Соцмережі DM (IG/TG/TT)"
    if sid == 1:
        if "{{fb}}" in us or "facebook" in us or us == "fb": return "site_ua", "Meta Ads (FB/IG)"
        if us in ("інстаграм","instagram","instagram.com","ig","l.instagram.com"): return "site_ua", "Instagram органіка (Лера)"
        if "tiktok" in us or us == "tt": return "site_ua", "TikTok Ads" if um == "paid" else "TikTok органіка (Лера)"
        if us in ("телеграм","telegram","t.me","tg"): return "site_ua", "Telegram (Лера)"
        if us == "google" and um == "cpc": return "site_ua", "Google Ads (PMax/Search)"
        if us == "google" and um == "organic": return "site_ua", "SEO (Google organic)"
        if "google" in us: return "site_ua", "Google інше (referral)"
        if um == "horoshop_trigger": return "site_ua", "Email: Horoshop тригери"
        if "sendpulse" in us: return "site_ua", "Email/TG: SendPulse"
        if us in ("mailchimp","email") or um == "email": return "site_ua", "Email: Mailchimp/інші"
        if us == "sms": return "site_ua", "SMS"
        if us in ("(direct)","direct"): return "site_ua", "Direct (прямі заходи)"
        if us == "chatgpt.com" or "perplexity" in us or "gemini" in us: return "site_ua", "AI-асистенти (GEO)"
        if not us: return "site_ua", "Сайт без UTM (direct/втрачено)"
        return "site_ua", f"Інше: {us[:24]}"
    return "other", f"Інше джерело: {sname[:28]}"

def family(name):
    n = (name or "").lower()
    for pat, fam in [
        (r"5\.7","Штани Gen 5.7"),(r"5\.6","Штани Gen 5.6"),(r"5\.4","Штани Gen 5.4"),
        (r"lite|лайт","Штани Lite"),(r"ультралайт|ultral","Штани Ultralight"),
        (r"убакс|ubacs|бойова сорочка","Убакси"),(r"куртк|jacket","Куртки"),
        (r"фліс|fleece","Фліс"),(r"шорти","Шорти"),(r"футболк|t-shirt","Футболки"),
        (r"терм","Термобілизна"),(r"шкарпет","Шкарпетки"),(r"панам|кепк|шапк|бейсбол","Головні убори"),
        (r"ремін|пояс|belt","Ремені"),(r"наколін|налокіт","Захист EVA"),
        (r"сумк|чохол|bag","Сумки/чохли"),(r"комплект|set","Комплекти"),
        (r"дощовик|пончо","Дощовики"),(r"сорочка","Сорочки casual"),(r"труси","Білизна"),
        (r"штани|pants|брюки","Штани інші"),
    ]:
        if re.search(pat, n): return fam
    return "Інше"

def camp_label(m, ch):
    uc = (m.get("utm_campaign") or "").strip(); ut = (m.get("utm_content") or "").strip()
    if ch == "Meta Ads (FB/IG)":
        stage = re.search(r"(TOF|MOF|BOF)", ut or "")
        prod = re.sub(r"\{\{|\}\}|_?\{?ad_id\}?_?|TOF|MOF|BOF", "", ut).strip("_ ") if ut else ""
        base = uc.replace("{{","").replace("}}","") or "FB"
        return (base + " · " + (stage.group(1) if stage else "?") + (" · " + prod if prod else ""))[:46]
    return (uc or "(без campaign)")[:46]

PAID_CH = ("Meta Ads (FB/IG)","TikTok Ads","Google Ads (PMax/Search)","Email: Mailchimp/інші",
           "Email: Horoshop тригери","Email/TG: SendPulse","TikTok органіка (Лера)",
           "Telegram (Лера)","SMS","Instagram органіка (Лера)")

# ── розбір замовлень ───────────────────────────────────────────────
orders, pipeline = [], []
for o in RAW["orders"]:
    s = STATUS.get(o.get("status_id"), {})
    gid = s.get("group_id"); sname = s.get("name", "?")
    closed_raw = o.get("closed_at")
    try: dt_created = datetime.datetime.fromisoformat(o["created_at"].replace("Z","+00:00")).date()
    except Exception: continue
    grp, ch = classify(o)
    fx = USD_UAH if grp == "intl" else 1
    if gid not in (DONE_GROUP, CANCEL_GROUP) or not closed_raw:
        pipeline.append({"id": o.get("id"), "date": dt_created, "age": (TODAY - dt_created).days,
                         "group": grp, "channel": ch, "status": sname, "status_group": gid,
                         "sum": (o.get("grand_total") or 0) * fx,
                         "source": SOURCES.get(o.get("source_id"), "?")})
        continue
    try: dt = datetime.datetime.fromisoformat(closed_raw.replace("Z","+00:00")).date()
    except Exception: continue
    orders.append({"date": dt, "created": dt_created, "grand_total": (o.get("grand_total") or 0)*fx,
        "margin": (o.get("margin_sum") or 0)*fx, "group": grp, "channel": ch,
        "cancelled": gid == CANCEL_GROUP, "status": sname,
        "campaign": camp_label(o.get("marketing") or {}, ch) if ch in PAID_CH else None,
        "products": [(p.get("sku"), p.get("name"), p.get("quantity") or 1, p.get("price_sold") or 0)
                     for p in (o.get("products") or [])]})

def between(d,a,b): return a <= d <= b
def agg(rows):
    r = {"orders":0,"revenue":0,"margin":0,"cancelled":0}
    for o in rows:
        if o["cancelled"]: r["cancelled"] += 1; continue
        r["orders"] += 1; r["revenue"] += o["grand_total"]; r["margin"] += o["margin"]
    r["aov"] = round(r["revenue"]/r["orders"]) if r["orders"] else 0
    return r

cur       = [o for o in orders if between(o["date"], MON_START, TODAY)]
prev_same = [o for o in orders if between(o["date"], PREV_START, PREV_SAME_END)]
prev_full = [o for o in orders if between(o["date"], PREV_START, prev_last)]

channels = {}
for label, rows in (("cur", cur), ("prev", prev_same), ("pfull", prev_full)):
    for o in rows:
        c = channels.setdefault(o["channel"], {"group": o["group"], "cur": [], "prev": [], "pfull": []})
        c[label].append(o)
chan_stats = []
for ch, c in channels.items():
    a, b, f = agg(c["cur"]), agg(c["prev"]), agg(c["pfull"])
    delta = round((a["revenue"]-b["revenue"])/b["revenue"]*100) if b["revenue"] else (100 if a["revenue"] else 0)
    chan_stats.append({"channel": ch, "group": c["group"],
        **{f"cur_{k}":v for k,v in a.items()}, **{f"prev_{k}":v for k,v in b.items()},
        "pfull_revenue": f["revenue"], "delta_rev_pct": delta})
chan_stats.sort(key=lambda x: -x["cur_revenue"])

groups_order = ["site_ua","bot","b2b","intl","manual","social_leads","other"]

# ── PERIOD-AWARE FACTS: [dateIdx, chIdx, orders, revenue, margin, cancelled] ──
DATES = [str(DATA_START + datetime.timedelta(days=i)) for i in range((TODAY - DATA_START).days + 1)]
DI = {d:i for i,d in enumerate(DATES)}
CH_LIST = sorted({o["channel"] for o in orders} | {p["channel"] for p in pipeline})
CI = {c:i for i,c in enumerate(CH_LIST)}
CH_GROUP = {}
for o in orders: CH_GROUP[o["channel"]] = o["group"]
for p in pipeline: CH_GROUP.setdefault(p["channel"], p["group"])

fbucket = defaultdict(lambda: [0,0.0,0.0,0])
for o in orders:
    di = DI.get(str(o["date"]))
    if di is None: continue
    k = (di, CI[o["channel"]])
    if o["cancelled"]: fbucket[k][3] += 1
    else:
        fbucket[k][0] += 1; fbucket[k][1] += o["grand_total"]; fbucket[k][2] += o["margin"]
FACTS = [[k[0], k[1], v[0], round(v[1]), round(v[2]), v[3]] for k, v in sorted(fbucket.items())]

# ── товарні групи по днях ──
FAM_LIST = sorted({family(n) for o in orders for _,n,_,_ in o["products"]})
FMI = {f:i for i,f in enumerate(FAM_LIST)}
fam_b = defaultdict(lambda: [0.0, 0])
for o in orders:
    if o["cancelled"]: continue
    di = DI.get(str(o["date"]))
    if di is None: continue
    for sku, name, qty, price in o["products"]:
        k = (di, FMI[family(name)]); fam_b[k][0] += qty*price; fam_b[k][1] += qty
FAM_FACTS = [[k[0], k[1], round(v[0]), v[1]] for k, v in sorted(fam_b.items())]

# ── SKU × день (топ-140 за виручку у вибірці) ──
sku_rev = Counter(); sku_name = {}
for o in orders:
    if o["cancelled"]: continue
    for sku, name, qty, price in o["products"]:
        if not sku: continue
        sku_rev[sku] += qty*price; sku_name.setdefault(sku, name or "")
TOP_SKUS = [s for s,_ in sku_rev.most_common(140)]
SI = {s:i for i,s in enumerate(TOP_SKUS)}
stock = {}
for off in RAW["offers"]:
    sk = off.get("sku")
    if not sk: continue
    st = stock.setdefault(sk, {"name": (off.get("product") or {}).get("name") or "", "qty": 0})
    st["qty"] += off.get("quantity") or 0
SKU_LIST = [{"sku": s, "name": (sku_name.get(s) or stock.get(s,{}).get("name") or "")[:74],
             "stock": stock.get(s, {}).get("qty", 0)} for s in TOP_SKUS]
sku_b = defaultdict(lambda: [0, 0.0])
for o in orders:
    if o["cancelled"]: continue
    di = DI.get(str(o["date"]))
    if di is None: continue
    for sku, name, qty, price in o["products"]:
        if sku not in SI: continue
        k = (di, SI[sku]); sku_b[k][0] += qty; sku_b[k][1] += qty*price
SKU_FACTS = [[k[0], k[1], v[0], round(v[1])] for k, v in sorted(sku_b.items())]

# ── кампанії × день ──
CAMP_LIST, KI = [], {}
camp_b = defaultdict(lambda: [0, 0.0, 0])
for o in orders:
    if not o["campaign"]: continue
    di = DI.get(str(o["date"]))
    if di is None: continue
    key = (o["channel"], o["campaign"])
    if key not in KI:
        KI[key] = len(CAMP_LIST); CAMP_LIST.append({"channel": key[0], "campaign": key[1]})
    k = (di, KI[key])
    if o["cancelled"]: camp_b[k][2] += 1
    else: camp_b[k][0] += 1; camp_b[k][1] += o["grand_total"]
CAMP_FACTS = [[k[0], k[1], v[0], round(v[1]), v[2]] for k, v in sorted(camp_b.items())]

# ── причини скасувань × день × канал ──
CANC_LIST = sorted({o["status"] for o in orders if o["cancelled"]})
RI = {r:i for i,r in enumerate(CANC_LIST)}
canc_b = defaultdict(lambda: [0, 0.0])
for o in orders:
    if not o["cancelled"]: continue
    di = DI.get(str(o["date"]))
    if di is None: continue
    k = (di, RI[o["status"]], CI[o["channel"]])
    canc_b[k][0] += 1; canc_b[k][1] += o["grand_total"]
CANC_FACTS = [[k[0], k[1], k[2], v[0], round(v[1])] for k, v in sorted(canc_b.items())]

# ── місячна динаміка ──
mon_rev = defaultdict(lambda: defaultdict(float))
for o in orders:
    if o["cancelled"]: continue
    mon_rev[(o["date"].year, o["date"].month)][o["group"]] += o["grand_total"]
mkeys = sorted(mon_rev.keys())
month_labels, month_partial = [], []
for (y,m) in mkeys:
    lbl = f"{UA_MON3[m]} {str(y)[2:]}"
    first_full = (y,m) > (DATA_START.year, DATA_START.month) or DATA_START.day == 1
    if (y,m) == (TODAY.year, TODAY.month): lbl += " MTD"; month_partial.append(True)
    elif not first_full: lbl += " ч."; month_partial.append(True)
    else: month_partial.append(False)
    month_labels.append(lbl)
month_series = {g: [round(mon_rev[k].get(g,0)) for k in mkeys] for g in groups_order}

# ── PIPELINE «В РОБОТІ» ─────────────────────────────────────────────
AGE_BUCKETS = [("0–3 дні",0,3,"ok"),("4–7 днів",4,7,"ok"),("8–14 днів",8,14,"warn"),
               ("15–30 днів",15,30,"serious"),("30+ днів",31,99999,"critical")]
pipe_by_status, pipe_by_ch, pipe_by_age = defaultdict(lambda:[0,0.0,0]), defaultdict(lambda:[0,0.0]), []
for p in pipeline:
    st = pipe_by_status[(p["status"], p["status_group"])]
    st[0] += 1; st[1] += p["sum"]; st[2] += p["age"]
    c = pipe_by_ch[p["channel"]]; c[0] += 1; c[1] += p["sum"]
for lbl, a, b, sev in AGE_BUCKETS:
    rows = [p for p in pipeline if a <= p["age"] <= b]
    pipe_by_age.append({"bucket": lbl, "orders": len(rows), "sum": round(sum(r["sum"] for r in rows)), "sev": sev})
STALE_DAYS = 14
stale = sorted([p for p in pipeline if p["age"] >= STALE_DAYS], key=lambda p: -p["sum"])[:20]

# історична конверсія «в роботі → закрито»: замовлення, створені 30-100 днів тому і вже вирішені
res_w = [o for o in orders if (TODAY - o["created"]).days >= 30]
res_done = sum(1 for o in res_w if not o["cancelled"])
close_rate = round(res_done / len(res_w), 3) if res_w else 0.85
pipe_total_sum = sum(p["sum"] for p in pipeline)

PIPE = {
    "orders": len(pipeline), "sum": round(pipe_total_sum),
    "month_orders": sum(1 for p in pipeline if p["date"] >= MON_START),
    "month_sum": round(sum(p["sum"] for p in pipeline if p["date"] >= MON_START)),
    "close_rate": close_rate, "expected": round(pipe_total_sum * close_rate),
    "by_status": sorted([{"status": k[0], "group": k[1], "orders": v[0], "sum": round(v[1]),
                          "avg_age": round(v[2]/v[0],1)} for k,v in pipe_by_status.items()],
                        key=lambda x: -x["sum"]),
    "by_channel": sorted([{"channel": k, "group": CH_GROUP.get(k,"other"), "orders": v[0], "sum": round(v[1])}
                          for k,v in pipe_by_ch.items()], key=lambda x: -x["sum"]),
    "by_age": pipe_by_age,
    "stale": [{"id": p["id"], "created": str(p["date"]), "age": p["age"], "channel": p["channel"],
               "status": p["status"], "sum": round(p["sum"]), "source": p["source"]} for p in stale],
    "stale_days": STALE_DAYS,
    "stale_sum": round(sum(p["sum"] for p in pipeline if p["age"] >= STALE_DAYS)),
    "stale_orders": sum(1 for p in pipeline if p["age"] >= STALE_DAYS),
}

# ── склад × попит (14д) ──
sold14 = Counter()
for o in orders:
    if o["cancelled"] or not (D14 < o["date"] <= TODAY): continue
    for sku, name, qty, price in o["products"]: sold14[sku] += qty
top_stock = []
for sku, q14 in sold14.most_common(30):
    st = stock.get(sku, {"name":"?","qty":0})
    rate14 = q14/14
    cover = round(st["qty"]/rate14) if rate14 > 0 else 999
    top_stock.append({"sku": sku, "name": (sku_name.get(sku) or st["name"])[:74],
                      "sold14": q14, "stock": st["qty"], "cover_days": cover})

# ── families MTD vs prev ──
def prod_agg(rows):
    fam_r = Counter()
    for o in rows:
        if o["cancelled"]: continue
        for sku, name, qty, price in o["products"]: fam_r[family(name)] += qty*price
    return fam_r
fam_cur, fam_prev = prod_agg(cur), prod_agg(prev_same)
fam_table = []
for f in set(list(fam_cur)+list(fam_prev)):
    cv, pv = fam_cur.get(f,0), fam_prev.get(f,0)
    fam_table.append({"family": f, "cur": round(cv), "prev": round(pv),
                      "delta_pct": round((cv-pv)/pv*100) if pv else (100 if cv else 0)})
fam_table.sort(key=lambda x: -x["cur"])

# ── прогноз ──
prev_days = (prev_last - PREV_START).days + 1
forecast, total_fc = {}, 0
for g in groups_order:
    mtd = sum(o["grand_total"] for o in cur if not o["cancelled"] and o["group"]==g)
    r14 = sum(o["grand_total"] for o in orders if not o["cancelled"] and o["group"]==g and D14 < o["date"] <= TODAY)/14
    rpm = sum(o["grand_total"] for o in prev_full if not o["cancelled"] and o["group"]==g)/prev_days
    fc = round(mtd + (0.6*r14 + 0.4*rpm) * REM_DAYS)
    forecast[g] = fc; total_fc += fc
cur_all, prev_all, pfull_all = agg(cur), agg(prev_same), agg(prev_full)

# ── insights ──
insights = []
fb_literal = sum(1 for o in RAW["orders"] if ((o.get("marketing") or {}).get("utm_source") or "") == "{{fb}}")
if fb_literal:
    insights.append(f"UTM-шаблон Meta зламаний: {fb_literal} замовлень у вибірці мають literal «{{{{fb}}}}» замість джерела. Фікс у Meta Ads Manager, URL parameters: utm_source=facebook&utm_medium=paid&utm_campaign={{{{campaign.name}}}}&utm_content={{{{ad.name}}}}.")
no_utm = next((c for c in chan_stats if "без UTM" in c["channel"]), None)
if no_utm and cur_all["revenue"] and no_utm["cur_revenue"]/cur_all["revenue"] >= 0.05:
    insights.append(f"«Сайт без UTM» = {round(no_utm['cur_revenue']/cur_all['revenue']*100)}% виручки — мітки губляться (trailing slash перед ?utm_ на uatac.ua).")
bot = next((c for c in chan_stats if c["group"]=="bot"), None)
if bot and bot["cur_cancelled"] >= 3 and bot["cur_cancelled"] > bot["cur_orders"]:
    insights.append(f"Леся-бот: {bot['cur_cancelled']} скасувань проти {bot['cur_orders']} продажів за місяць — перевірити дублікати замовлень бота.")
sms_c = next((c for c in chan_stats if c["channel"]=="SMS"), None)
if sms_c and sms_c["pfull_revenue"] > 10000 and sms_c["cur_revenue"] == 0:
    insights.append(f"SMS дав {fmt_int(sms_c['pfull_revenue'])} ₴ минулого місяця і 0 ₴ у поточному — розсилки зупинилися, канал робочий.")
if PIPE["stale_orders"]:
    insights.append(f"«В роботі» зависло {PIPE['stale_orders']} замовлень старше {STALE_DAYS} днів на {fmt_int(PIPE['stale_sum'])} ₴ — або дозакрити, або перевести у скасовані, інакше воронка бреше.")

# ── тактика дня ──
tactics = []
drops = sorted(chan_stats, key=lambda c: c["cur_revenue"]-c["prev_revenue"])
gains = sorted(chan_stats, key=lambda c: c["prev_revenue"]-c["cur_revenue"])
used = set()
d0 = drops[0] if drops else None
if d0 and d0["prev_revenue"] - d0["cur_revenue"] > 15000:
    act = ("перевірити трафік і рекламу на uatac.shop, підняти INTL-кампанії" if d0["group"]=="intl"
           else "Скопик: дотиснути дилерів, що замовляли минулого місяця" if d0["group"]=="b2b"
           else "Лера: обдзвін топ-5 клієнтів місяця сьогодні" if d0["group"]=="manual"
           else "перевірити трафік, наявність топових позицій і ціну")
    tactics.append(f"<b>{d0['channel']}</b> {d0['delta_rev_pct']}% (−{fmt_int(d0['prev_revenue']-d0['cur_revenue'])} ₴) — {act}.")
    used.add(d0["channel"])
g0 = gains[0] if gains else None
if g0 and g0["cur_revenue"] - g0["prev_revenue"] > 15000 and g0["channel"] not in used:
    scale = ("бюджет +20%/тиждень, ставки не чіпати" if g0["group"]=="site_ua"
             else "Скопик: тримати темп, зафіксувати повторні партії на осінь" if g0["group"]=="b2b"
             else "тримати акцент, не міняти умов")
    tactics.append(f"<b>{g0['channel']}</b> {g0['delta_rev_pct']:+d}% — масштабувати: {scale}.")
    used.add(g0["channel"])
for c in sorted(chan_stats, key=lambda c: -c["prev_revenue"]):
    if len(tactics) >= 6: break
    if c["channel"] in used: continue
    if c["cur_revenue"] == 0 and c["prev_revenue"] >= 5000:
        fix = "полагодити UTM-шаблон, бюджет не піднімати доки атрибуція сліпа" if "Meta" in c["channel"] else "перезапустити розсилки"
        tactics.append(f"<b>{c['channel']}</b> 0 ₴ проти {fmt_int(c['prev_revenue'])} ₴ — {fix}.")
        used.add(c["channel"])
for c in sorted(chan_stats, key=lambda c: -c["cur_cancelled"]):
    if len(tactics) >= 6: break
    if c["channel"] in used or c["cur_cancelled"] < 3: continue
    if c["cur_cancelled"] >= max(c["cur_orders"] * 0.25, 3):
        tactics.append(f"<b>{c['channel']}</b> {c['cur_cancelled']} скасувань на {c['cur_orders']} продажів — розібрати причини (дублі/недозвон).")
        used.add(c["channel"])
stockouts = [t for t in top_stock if t["stock"]==0 and t["sold14"]>=3]
low = [t for t in top_stock if 0 < t["cover_days"] <= 14 and t["sold14"]>=3]
grow_fam = [f for f in fam_table if f["delta_pct"] >= 60 and f["cur"] >= 20000]
if len(tactics) < 6 and (stockouts or low):
    parts = []
    if stockouts: parts.append(f"стокаут: {stockouts[0]['name'].split('|')[0].strip()[:38]}")
    if low: parts.append(f"{len(low)} поз. з покриттям <14 днів")
    tactics.append("<b>Склад</b> — " + "; ".join(parts) + " — поповнити, зняти з акцентів.")
if len(tactics) < 6 and grow_fam:
    tactics.append(f"<b>{grow_fam[0]['family']}</b> {grow_fam[0]['delta_pct']:+d}% — підняти в PMax asset groups та email.")
for c in drops:
    if len(tactics) >= 6: break
    if c["channel"] in used or c["delta_rev_pct"] >= -15 or c["prev_revenue"] < 3000: continue
    tactics.append(f"<b>{c['channel']}</b> {c['delta_rev_pct']}% — перевірити, чи не впав трафік/наявність топових позицій.")
    used.add(c["channel"])
tactics = tactics[:6]

def owner_for(ck, grp=None):
    if ck == "__stock__": return "Антон Нестерук"
    if ck == "__pipe__": return "Лера Нестерук"
    if ck == "__assort__": return "Serhii"
    if ck == "Shopify INTL": return "Serhii"
    if ck.startswith("B2B"): return "Скопик"
    if ck.startswith("Офіс") or ck == "SMS": return "Лера"
    if any(k in ck for k in ("Email","Telegram","Instagram","TikTok органіка")): return "Лера"
    return "Serhii"

# ── журнал рішень ──
try: DEC = json.load(open(DEC_PATH))
except Exception: DEC = {"decisions": []}

def rev_day(channel_key, a, b):
    days_n = max((b-a).days + 1, 1)
    rev = sum(o["grand_total"] for o in orders if not o["cancelled"] and o["channel"]==channel_key and a <= o["date"] <= b)
    return rev/days_n

for d in DEC["decisions"]:
    ck = d["channel_key"]; cd = datetime.date.fromisoformat(d["created"])
    if ck.startswith("__") or d["status"] in ("dropped",):
        d["before"]=d["after"]=None; d["effect_pct"]=None
        d["verdict"] = d.get("manual_verdict") or ("pending" if d["status"]!="done" else "done")
        continue
    before = rev_day(ck, cd - datetime.timedelta(days=7), cd)
    days_after = (TODAY - cd).days
    after = rev_day(ck, cd + datetime.timedelta(days=1), TODAY) if days_after >= 1 else None
    d["before"] = round(before); d["after"] = round(after) if after is not None else None
    if d.get("manual_verdict"):
        d["verdict"] = d["manual_verdict"]; d["effect_pct"] = round((after-before)/before*100) if (after is not None and before) else None
    elif days_after < 4:
        d["verdict"] = "pending"; d["effect_pct"] = round((after-before)/before*100) if (after is not None and before) else None
    else:
        eff = round((after-before)/before*100) if before else (100 if after else 0)
        d["effect_pct"] = eff
        d["verdict"] = "helped" if eff >= 15 else ("hurt" if eff <= -15 else "neutral")

open_keys = {d["channel_key"] for d in DEC["decisions"] if d["status"] in ("open","in_progress")}
next_id = max([d["id"] for d in DEC["decisions"]], default=0) + 1
for t in tactics:
    plain = re.sub(r"<[^>]+>", "", t)
    ck = None
    for c in chan_stats:
        if c["channel"] in plain: ck = c["channel"]; break
    if ck and ck not in open_keys:
        DEC["decisions"].append({"id": next_id, "created": str(TODAY), "channel_key": ck, "owner": owner_for(ck),
            "action": plain[:180], "status": "open", "manual_verdict": None,
            "before": round(rev_day(ck, TODAY - datetime.timedelta(days=7), TODAY)), "after": None,
            "effect_pct": None, "verdict": "pending", "note": "auto"})
        open_keys.add(ck); next_id += 1
# задача по зависаннях у воронці
if PIPE["stale_orders"] >= 3 and "__pipe__" not in open_keys:
    DEC["decisions"].append({"id": next_id, "created": str(TODAY), "channel_key": "__pipe__", "owner": owner_for("__pipe__"),
        "action": f"Розібрати {PIPE['stale_orders']} завислих замовлень старше {STALE_DAYS} днів на {fmt_int(PIPE['stale_sum'])} ₴ — дозакрити або перевести у скасовані",
        "status": "open", "manual_verdict": None, "before": None, "after": None,
        "effect_pct": None, "verdict": "pending", "note": "auto"})
    next_id += 1
json.dump(DEC, open(DEC_PATH, "w"), ensure_ascii=False, indent=1)
decisions_out = DEC["decisions"]

def build_details(d):
    ck = d["channel_key"]
    c = next((x for x in chan_stats if x["channel"] == ck), None)
    why, how = [], []
    if c:
        why.append(f"MTD: {fmt_int(c['cur_revenue'])} ₴ / {c['cur_orders']} зам. проти {fmt_int(c['prev_revenue'])} ₴ / {c['prev_orders']} зам. за той самий відрізок минулого місяця ({c['delta_rev_pct']:+d}%).")
        if c["cur_aov"]: why.append(f"Середній чек каналу {fmt_int(c['cur_aov'])} ₴, маржа MTD {fmt_int(c['cur_margin'])} ₴.")
        if c["cur_cancelled"]: why.append(f"Скасувань у каналі за місяць: {c['cur_cancelled']}.")
        if c["pfull_revenue"]: why.append(f"Повний минулий місяць канал дав {fmt_int(c['pfull_revenue'])} ₴ — це і є орієнтир норми.")
        pc = next((x for x in PIPE["by_channel"] if x["channel"] == ck), None)
        if pc: why.append(f"У роботі зараз: {pc['orders']} зам. на {fmt_int(pc['sum'])} ₴ — вони ще можуть дозакритись у цей місяць.")
    if "Meta" in ck:
        how = ["Ads Manager → Налаштування кампанії → URL parameters: підставити реальні макроси кампанії/оголошення замість плейсхолдерів, що не розкриваються.",
               "Перевірити на тестовому кліку, що в KeyCRM приходить джерело facebook і назва кампанії, а не фігурні дужки.",
               "Оновити креативи (частота > 2 = вигорання), запустити 2-3 нові варіанти.",
               "Бюджет не піднімати, доки в CRM не видно реальних кампаній."]
    elif "Google Ads" in ck:
        how = ["Підняти денний бюджет PMax максимум на 20% за тиждень (до 840 ₴/день).",
               "Ставки/tROAS цього ж тижня НЕ чіпати — два зміни одночасно ламають навчання.",
               "Перевірити search terms, додати мінус-слова.",
               "Позиції без конверсій при витраті >150 ₴ за 14 днів — виключити з фіду."]
    elif "Офіс" in ck or "телефон" in ck:
        how = ["Вивантажити топ-5 клієнтів минулого місяця з KeyCRM за сумою.",
               "Обдзвін сьогодні: осіння пропозиція + нагадування про демісезон.",
               "Кожен дзвінок фіксувати в CRM з коментарем — інакше ефект не порахується.",
               "Ціль: повернути канал до рівня минулого місяця."]
    elif ck == "SMS":
        how = ["Перевірити баланс і статус відправника у сервісі розсилок.",
               "Запустити сегмент «купували 60-180 днів тому» з осінньою пропозицією.",
               "Обов'язково UTM: source sms, medium sms, campaign з датою.",
               "Один запуск на тиждень, дивитись виручку на запуск."]
    elif "Леся" in ck or "бот" in ck.lower():
        how = ["Вивантажити скасовані замовлення бота за 30 днів.",
               "Перевірити гіпотезу дублів: один клієнт — кілька замовлень протягом години.",
               "Якщо дублі — додати перевірку існуючого відкритого замовлення перед створенням нового.",
               "Якщо недозвон — передавати ліда менеджеру після 2 спроб."]
    elif ck == "__stock__":
        how = ["Антон: перелік позицій зі стокаутом і покриттям <14 днів.",
               "Врахувати lead-time 1-2 місяці — замовляти зараз, а не коли закінчиться.",
               "До поповнення прибрати позицію з рекламних акцентів і email.",
               "Перевірити розмірну сітку: часто б'є не товар, а 2-3 ходових розміри."]
        why.append("Позиції з нульовим залишком продовжують отримувати кліки — це прямий злив бюджету.")
    elif ck == "__pipe__":
        how = ["Вивантажити список завислих замовлень (він у блоці «В роботі» → «Зависло»).",
               "По кожному: дозвін клієнту або переведення в скасовані з причиною.",
               "Замовлення «Прибув у відділення» старші 7 днів — нагадування SMS про забір.",
               "Мета: тримати вік воронки ≤ 14 днів, інакше прогноз місяця завищений."]
        why.append(f"Історична конверсія «в роботі → закрито» = {round(close_rate*100)}%. З {fmt_int(PIPE['sum'])} ₴ очікувано дозакриється ~{fmt_int(PIPE['expected'])} ₴.")
    elif ck == "__assort__":
        how = ["Додати групу в asset groups PMax окремим блоком.",
               "Поставити в найближчу email-розсилку як головний блок.",
               "Перевірити наявність усіх розмірів перед підняттям акценту."]
        why.append("Група росте сама — підсилення дає найдешевший приріст.")
    elif "TikTok" in ck:
        how = ["Розділяти платні кампанії й органіку Лери в UTM (medium paid проти власних лінків).",
               "Дивитись, які креативи дали замовлення, масштабувати їх.",
               "Слідкувати за скасуваннями — у TikTok вища частка імпульсних замовлень."]
    elif "Email" in ck or "Horoshop" in ck:
        how = ["Перевірити, що тригерні листи (кинутий кошик, реєстрація) активні.",
               "Додати блок допродажу до товару в листі.",
               "UTM обов'язково з назвою кампанії, інакше канал не видно."]
    elif ck == "Shopify INTL":
        how = ["Перевірити трафік і замовлення в адмінці Shopify (у KeyCRM UTM з Shopify не приходять).",
               "Подивитись, чи працюють INTL-кампанії та чи не впав органічний трафік на uatac.shop.",
               "Перевірити наявність ходових позицій у INTL-каталозі.",
               "Написати повторним клієнтам INTL з пропозицією осінньої лінійки."]
        why.append(f"Суми конвертовані з USD у грн за курсом {USD_UAH} ₴/$.")
    elif "B2B" in ck:
        how = ["Скопик: перелік дилерів, що замовляли минулого місяця й мовчать зараз.",
               "Нагадати про осінньо-зимову партію з урахуванням черги виробництва 2-4 місяці.",
               "Тримати умови незмінними: знижка від РРЦ, 50/50, без доставки."]
    else:
        how = ["Перевірити динаміку каналу за тиждень.",
               "Знайти конкретну причину: трафік, наявність, ціна, комунікація.",
               "Зафіксувати дію в журналі — ефект порахується автоматично."]
    if d.get("before") is not None:
        why.append(f"База для оцінки: {fmt_int(d['before'])} ₴/день за 7 днів до рішення. Вердикт з'явиться на 4-й день після дати рішення.")
    return {"why": why, "how": how}

for d in decisions_out:
    d["details"] = d.get("details_manual") or build_details(d)


# ── РІК ДО РОКУ + МОДЕЛЬ ЦІЛІ ──────────────────────────────────────
def _load(path):
    try: return json.load(open(path))
    except Exception: return None
def _yoy_months(BL):
    if not BL: return []
    out = []
    for m in sorted(BL["months"]):
        v = BL["months"][m]
        lyk = f"{int(m[:4])-1}{m[4:]}"
        lyv = BL["months"].get(lyk) or {}
        yoy = round((v["revenue"] - lyv["revenue"]) / lyv["revenue"] * 100) if lyv.get("revenue") else None
        out.append({"m": m, "revenue": v["revenue"], "orders": v["orders"], "aov": v["aov"], "yoy": yoy})
    return out[-15:]

BL = _load(BASELINE)
SP = _load(SPEND) or {}

def ly_slice(a, b):
    """Той самий відрізок минулого року за календарними датами."""
    if not BL: return None
    di = {d: i for i, d in enumerate(BL["dates"])}
    want = set()
    d = a
    while d <= b:
        try: want.add(str(d.replace(year=d.year - 1)))
        except ValueError: pass          # 29 лютого
        d += datetime.timedelta(days=1)
    idx = {di[x] for x in want if x in di}
    if not idx: return None
    r = {"revenue": 0, "orders": 0, "margin": 0, "cancelled": 0}
    for f in BL["facts"]:
        if f[0] in idx:
            r["orders"] += f[2]; r["revenue"] += f[3]; r["margin"] += f[4]; r["cancelled"] += f[5]
    r["aov"] = round(r["revenue"] / r["orders"]) if r["orders"] else 0
    r["cancel_pct"] = round(r["cancelled"] / (r["orders"] + r["cancelled"]) * 100) if (r["orders"] + r["cancelled"]) else 0
    r["covered"] = len(idx)
    return r

def ly_month(y, m):
    if not BL: return None
    return BL["months"].get(f"{y-1}-{m:02d}")

LY_SAME = ly_slice(MON_START, TODAY)
LY_MON  = ly_month(TODAY.year, TODAY.month)
PREV_M  = BL["months"].get(f"{PREV_START.year}-{PREV_START.month:02d}") if BL else None
PREV_LY = ly_month(PREV_START.year, PREV_START.month)

# Фаза: якщо минулий повний місяць перебив свій торішній — режим зростання, інакше відновлення
if PREV_M and PREV_LY and PREV_LY.get("revenue"):
    PHASE = "grow" if PREV_M["revenue"] >= PREV_LY["revenue"] else "recover"
else:
    PHASE = "recover"
G = 0.10 if PHASE == "grow" else 0.0

if MONTH_TARGET:
    TARGET = MONTH_TARGET; TARGET_BASIS = "задано вручну"
elif LY_MON and LY_MON.get("revenue"):
    TARGET = LY_MON["revenue"] * (1 + G)
    TARGET_BASIS = (f"{UA_MON[TODAY.month]} {TODAY.year-1}" + (f" +{int(G*100)}%" if G else " (повернення до рівня)"))
else:
    TARGET = pfull_all["revenue"]; TARGET_BASIS = f"рівень {UA_MON_GEN[PREV_START.month]}"
TARGET = round(TARGET)
GAP = max(0, TARGET - total_fc)

# Три важелі: Виручка = Замовлення × Чек × (1 − скасування)
cur_cancel_pct = round(cur_all["cancelled"] / (cur_all["orders"] + cur_all["cancelled"]) * 100) if (cur_all["orders"] + cur_all["cancelled"]) else 0
days_gone = TODAY.day
pace_orders = cur_all["orders"] / days_gone if days_gone else 0
proj_orders = round(pace_orders * DAYS_IN_MON)
req_aov = round(TARGET / proj_orders) if proj_orders else 0
req_orders = round(TARGET / cur_all["aov"]) if cur_all["aov"] else 0

CM = cur_all["margin"] / cur_all["revenue"] if cur_all["revenue"] else 0.47
BREAKEVEN_MER = round(1 / CM, 2) if CM else None
mk_now = f"{TODAY.year}-{TODAY.month:02d}"
spend_now = SP.get(mk_now) or {}
spend_total = sum(v for k, v in spend_now.items() if isinstance(v, (int, float)))
MER = round(cur_all["revenue"] / spend_total, 2) if spend_total else None

YOY = {
    "available": bool(BL),
    "baseline_from": BL["from"] if BL else None, "baseline_to": BL["to"] if BL else None,
    "ly_same": LY_SAME, "ly_month": LY_MON, "prev_month": PREV_M, "prev_month_ly": PREV_LY,
    "delta_rev": round((cur_all["revenue"] - LY_SAME["revenue"]) / LY_SAME["revenue"] * 100) if (LY_SAME and LY_SAME["revenue"]) else None,
    "delta_orders": round((cur_all["orders"] - LY_SAME["orders"]) / LY_SAME["orders"] * 100) if (LY_SAME and LY_SAME["orders"]) else None,
    "delta_aov": round((cur_all["aov"] - LY_SAME["aov"]) / LY_SAME["aov"] * 100) if (LY_SAME and LY_SAME["aov"]) else None,
    "months": _yoy_months(BL),
}
TARGET_MODEL = {
    "target": TARGET, "basis": TARGET_BASIS, "phase": PHASE, "g": G, "gap": GAP,
    "forecast": total_fc, "fact": round(cur_all["revenue"]),
    "gap_per_day": round(GAP / REM_DAYS) if REM_DAYS else None,
    "breakeven_mer": BREAKEVEN_MER, "mer": MER, "spend": round(spend_total) if spend_total else None,
    "cm_pct": round(CM * 100),
    "levers": {
        "orders": {"now": cur_all["orders"], "projected": proj_orders,
                   "ly": (LY_SAME or {}).get("orders"), "delta": YOY["delta_orders"],
                   "required": req_orders},
        "aov": {"now": cur_all["aov"], "ly": (LY_SAME or {}).get("aov"), "delta": YOY["delta_aov"],
                "required": req_aov,
                "ratio": round(req_aov / cur_all["aov"], 2) if cur_all["aov"] else None},
        "cancel": {"now": cur_cancel_pct, "ly": (LY_SAME or {}).get("cancel_pct"),
                   "delta": (cur_cancel_pct - LY_SAME["cancel_pct"]) if LY_SAME else None},
    },
}

# ── ВОРОНКИ (звіт по каналах) + ПЛАН ЗАВДАНЬ ───────────────────────
try:
    PB = json.load(open(PLAYBOOK))
except Exception:
    PB = {"funnels": [], "tasks": []}

CH_STAT = {c["channel"]: c for c in chan_stats}

# місячна серія по каналу (для міні-тренду в картці воронки)
mon_ch = defaultdict(lambda: defaultdict(float))
for o in orders:
    if o["cancelled"]: continue
    mon_ch[o["channel"]][(o["date"].year, o["date"].month)] += o["grand_total"]

def merge_stats(keys):
    a = {"cur_revenue":0,"cur_orders":0,"cur_margin":0,"cur_cancelled":0,
         "prev_revenue":0,"prev_orders":0,"pfull_revenue":0}
    for k in keys:
        c = CH_STAT.get(k)
        if not c: continue
        for f in a: a[f] += c.get(f, 0)
    a["cur_aov"] = round(a["cur_revenue"]/a["cur_orders"]) if a["cur_orders"] else 0
    a["delta_rev_pct"] = round((a["cur_revenue"]-a["prev_revenue"])/a["prev_revenue"]*100) if a["prev_revenue"] else (100 if a["cur_revenue"] else 0)
    return a

def funnel_status(a):
    rate = a["cur_cancelled"]/(a["cur_orders"]+a["cur_cancelled"]) if (a["cur_orders"]+a["cur_cancelled"]) else 0
    d = a["delta_rev_pct"]
    if a["cur_revenue"] == 0 and a["prev_revenue"] >= 5000: return "broken", "зупинився"
    if rate >= 0.40 and a["cur_cancelled"] >= 3: return "broken", "скасування з'їдають канал"
    if d <= -25: return "dropping", "просідає"
    if rate >= 0.25 and a["cur_cancelled"] >= 3: return "unstable", "нестабільний"
    if d >= 15: return "growing", "росте"
    return "holding", "тримає"

FUN = []
for f in PB.get("funnels", []):
    keys = f.get("members") or [f["key"]]
    a = merge_stats(keys)
    pipe_sum = sum(p["sum"] for p in PIPE["by_channel"] if p["channel"] in keys)
    pipe_ord = sum(p["orders"] for p in PIPE["by_channel"] if p["channel"] in keys)
    months = []
    for (y, m) in mkeys:
        v = sum(mon_ch[k].get((y, m), 0) for k in keys)
        months.append(round(v))
    st, verdict = funnel_status(a)
    rate = a["cur_cancelled"]/(a["cur_orders"]+a["cur_cancelled"]) if (a["cur_orders"]+a["cur_cancelled"]) else 0
    FUN.append({"key": f["key"], "name": f["name"], "owner": f["owner"], "strategy": f["strategy"],
        "role": f["role"], "members": keys,
        "rev": round(a["cur_revenue"]), "orders": a["cur_orders"], "aov": a["cur_aov"],
        "margin": round(a["cur_margin"]), "cancelled": a["cur_cancelled"],
        "cancel_rate": round(rate*100), "prev": round(a["prev_revenue"]), "delta": a["delta_rev_pct"],
        "pfull": round(a["pfull_revenue"]), "pipe": round(pipe_sum), "pipe_orders": pipe_ord,
        "months": months, "share": round(a["cur_revenue"]/cur_all["revenue"]*100) if cur_all["revenue"] else 0,
        "status": st, "verdict": verdict})
FUN.sort(key=lambda x: -x["rev"])

# ── тригери завдань ────────────────────────────────────────────────
FUN_BY_KEY = {f["key"]: f for f in FUN}
top_fam = fam_table[0] if fam_table else {"family":"—","delta_pct":0,"cur":0}
grow_fam2 = next((f for f in fam_table if f["delta_pct"] >= 60 and f["cur"] >= 20000), None)

def ctx_for(ck):
    f = FUN_BY_KEY.get(ck)
    c = CH_STAT.get(ck)
    base = {
        "prev_month": UA_MON_GEN[PREV_START.month], "usd": USD_UAH,
        "stale_orders": PIPE["stale_orders"], "stale_days": STALE_DAYS,
        "stale_sum": fmt_int(PIPE["stale_sum"]), "close_rate": round(close_rate*100),
        "fb_literal": fb_literal, "target": fmt_int(TARGET), "forecast": fmt_int(total_fc),
        "ly_rev": fmt_int((LY_SAME or {}).get("revenue", 0)), "ly_orders": (LY_SAME or {}).get("orders", 0),
        "ly_aov": fmt_int((LY_SAME or {}).get("aov", 0)), "ly_month": UA_MON_GEN[TODAY.month] + " " + str(TODAY.year - 1),
        "req_aov": fmt_int(req_aov), "aov_ratio": (round(req_aov / cur_all["aov"], 2) if cur_all["aov"] else ""),
        "cur_aov": fmt_int(cur_all["aov"]), "proj_orders": proj_orders,
        "gap": fmt_int(GAP), "rem_days": REM_DAYS,
        "gap_per_day": fmt_int(GAP/REM_DAYS) if REM_DAYS else "—",
        "family": (grow_fam2 or top_fam)["family"],
        "family_delta": f"{(grow_fam2 or top_fam)['delta_pct']:+d}",
        "family_rev": fmt_int((grow_fam2 or top_fam)["cur"]),
        "rev": "0", "orders": 0, "prev_rev": "0", "delta": "0", "aov": "0",
        "pfull": "0", "cancelled": 0, "cancel_rate": 0, "share": 0,
    }
    src = f or ({"rev": c["cur_revenue"], "orders": c["cur_orders"], "prev": c["prev_revenue"],
                 "delta": c["delta_rev_pct"], "aov": c["cur_aov"], "pfull": c["pfull_revenue"],
                 "cancelled": c["cur_cancelled"],
                 "cancel_rate": round(c["cur_cancelled"]/(c["cur_orders"]+c["cur_cancelled"])*100) if (c["cur_orders"]+c["cur_cancelled"]) else 0,
                 "share": round(c["cur_revenue"]/cur_all["revenue"]*100) if cur_all["revenue"] else 0} if c else None)
    if src:
        base.update({"rev": fmt_int(src["rev"]), "orders": src["orders"],
            "prev_rev": fmt_int(src["prev"]), "delta": f"{src['delta']:+d}",
            "aov": fmt_int(src["aov"]), "pfull": fmt_int(src["pfull"]),
            "cancelled": src["cancelled"], "cancel_rate": src["cancel_rate"],
            "share": src["share"], "gap": fmt_int(max(0, src["prev"] - src["rev"]))})
    return base, src

_PH = re.compile(r"\{(\w+)\}")
def fill(text, ctx):
    return _PH.sub(lambda m: str(ctx.get(m.group(1), m.group(0))), text)

def fires(t, src):
    tr = t.get("trigger", {}); kind = tr.get("kind")
    if kind == "always": return True
    if kind == "broken_utm": return fb_literal > 0
    if kind == "stale_pipeline": return PIPE["stale_orders"] >= tr.get("min_orders", 3)
    if kind == "stockout": return bool([t2 for t2 in top_stock if t2["stock"] == 0 and t2["sold14"] >= 3])
    if kind == "family_growth": return grow_fam2 is not None
    if kind == "gap_to_target": return GAP > 0
    if not src: return False
    if kind == "zero_revenue": return src["rev"] == 0 and src["prev"] >= tr.get("min_prev", 5000)
    if kind == "drop": return src["delta"] <= tr.get("pct", -25) and src["prev"] >= 3000
    if kind == "growth": return src["delta"] >= tr.get("pct", 15) and src["rev"] >= 5000
    if kind == "cancel_rate":
        return src["cancel_rate"] >= tr.get("min", .25)*100 and src["cancelled"] >= tr.get("min_cancel", 3)
    if kind == "share_of_revenue": return src["share"] >= tr.get("min", .05)*100
    return False

PLAN = []
for t in PB.get("tasks", []):
    ctx, src = ctx_for(t["channel"])
    if not fires(t, src): continue
    PLAN.append({
        "id": t["id"], "channel": t["channel"],
        "funnel": (FUN_BY_KEY.get(t["channel"]) or {}).get("name") or
                  {"__pipe__":"Воронка","__stock__":"Склад","__assort__":"Асортимент","__target__":"План місяця"}.get(t["channel"], t["channel"]),
        "type": t["type"], "horizon": t["horizon"], "owner": t["owner"],
        "title": fill(t["title"], ctx),
        "why": [fill(x, ctx) for x in t["why"]],
        "how": [fill(x, ctx) for x in t["how"]],
        "goal": fill(t["goal"], ctx), "result": fill(t["result"], ctx),
        "strategy": t["strategy"], "kpi": fill(t.get("kpi", ""), ctx),
    })
HORIZON_ORDER = {"день": 0, "тиждень": 1, "місяць": 2, "квартал": 3}
PLAN.sort(key=lambda x: (0 if x["type"] == "tactical" else 1, HORIZON_ORDER.get(x["horizon"], 9)))

intl_monthly = []
for (y,m) in mkeys:
    rows_i = [o for o in orders if o["group"]=="intl" and (o["date"].year,o["date"].month)==(y,m)]
    a_i = agg(rows_i)
    intl_monthly.append({"month": f"{UA_MON3[m]} {str(y)[2:]}", "orders": a_i["orders"],
                         "revenue": round(a_i["revenue"]), "cancelled": a_i["cancelled"]})

ANALYSIS = {
    "generated_at": datetime.datetime.now().isoformat(), "today": str(TODAY),
    "data_start": str(DATA_START),
    "month_name": f"{UA_MON[TODAY.month]} {TODAY.year}", "month_short": UA_MON[TODAY.month],
    "period_cur": [str(MON_START), str(TODAY)],
    "period_prev": [str(PREV_START), str(PREV_SAME_END)],
    "prev_month_full": [str(PREV_START), str(prev_last)],
    "prev_month_name": UA_MON[PREV_START.month],
    "prev_month_gen": UA_MON_GEN[PREV_START.month], "month_gen": UA_MON_GEN[TODAY.month],
    "days_in_month": DAYS_IN_MON, "rem_days": REM_DAYS,
    "totals": {"cur": cur_all, "prev": prev_all, "pfull": pfull_all},
    "channels": chan_stats,
    "dates": DATES, "ch_list": CH_LIST, "ch_group": CH_GROUP, "facts": FACTS,
    "fam_list": FAM_LIST, "fam_facts": FAM_FACTS,
    "sku_list": SKU_LIST, "sku_facts": SKU_FACTS,
    "camp_list": CAMP_LIST, "camp_facts": CAMP_FACTS,
    "canc_list": CANC_LIST, "canc_facts": CANC_FACTS,
    "month_labels": month_labels, "month_series": month_series,
    "families": fam_table[:16], "top_stock": top_stock,
    "forecast30": forecast, "forecast30_total": total_fc,
    "usd_uah": USD_UAH, "basis": "closed",
    "pipeline": PIPE, "pipeline_all": PIPE["sum"], "pipeline_month": PIPE["month_sum"],
    "insights": insights, "tactics": tactics, "decisions": decisions_out,
    "funnels": FUN, "plan": PLAN,
    "target": TARGET, "gap_to_target": GAP, "target_source": TARGET_BASIS,
    "yoy": YOY, "target_model": TARGET_MODEL,
    "intl_monthly": intl_monthly,
    "group_labels": {"site_ua":"Сайт uatac.ua","bot":"Леся (AI-бот)","b2b":"B2B (дропи/дилери)",
                     "intl":"Shopify INTL","manual":"Офіс/телефон","social_leads":"Lead-форми/DM","other":"Інше"},
    "group_colors": {"site_ua":"#e66900","b2b":"#56a76a","intl":"#0a73aa","bot":"#ae3a6f",
                     "manual":"#9e5900","social_leads":"#00a7bc","other":"#8073e1"},
}
json.dump(ANALYSIS, open(OUT_DIR+"/analysis.json","w"), ensure_ascii=False, indent=1, default=str)
print(f"OK | {UA_MON[TODAY.month]} MTD: {fmt_int(cur_all['revenue'])} ₴ ({cur_all['orders']} зам.) vs 1–{PREV_SAME_END.day} {UA_MON[PREV_START.month]}: {fmt_int(prev_all['revenue'])} ₴")
print(f"В РОБОТІ: {PIPE['orders']} зам. / {fmt_int(PIPE['sum'])} ₴ · очікувано дозакриється {fmt_int(PIPE['expected'])} ₴ (close rate {round(close_rate*100)}%)")
print(f"Зависло >{STALE_DAYS}д: {PIPE['stale_orders']} зам. / {fmt_int(PIPE['stale_sum'])} ₴")
# ── history.csv: короткий денний зріз для довгої історії ──
HIST = os.environ.get("UATAC_HISTORY")
if HIST:
    import csv
    cols = ["date","revenue","orders","aov","margin","cancelled","pipeline_sum","pipeline_orders",
            "stale_sum","forecast","target"] + [f["name"] for f in FUN]
    row = {"date": str(TODAY), "revenue": round(cur_all["revenue"]), "orders": cur_all["orders"],
           "aov": cur_all["aov"], "margin": round(cur_all["margin"]), "cancelled": cur_all["cancelled"],
           "pipeline_sum": PIPE["sum"], "pipeline_orders": PIPE["orders"], "stale_sum": PIPE["stale_sum"],
           "forecast": total_fc, "target": round(TARGET)}
    for f in FUN: row[f["name"]] = f["rev"]
    rows, exists = [], os.path.exists(HIST)
    if exists:
        with open(HIST, newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r.get("date") != str(TODAY)]
    with open(HIST, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow(r)
        w.writerow(row)
    print(f"history → {HIST} ({len(rows)+1} рядків)")

print(f"воронок={len(FUN)} завдань у плані={len(PLAN)} (тактичних {sum(1 for p in PLAN if p['type']=='tactical')})")
print(f"ціль {fmt_int(TARGET)} ₴ ({TARGET_BASIS}, фаза {PHASE}) · прогноз {fmt_int(total_fc)} ₴ · розрив {fmt_int(GAP)} ₴")
if LY_SAME: print(f"YoY той самий відрізок: {fmt_int(LY_SAME['revenue'])} ₴ / {LY_SAME['orders']} зам / AOV {fmt_int(LY_SAME['aov'])} → зараз {YOY['delta_rev']:+d}% виручка, {YOY['delta_orders']:+d}% замовлення, {YOY['delta_aov']:+d}% чек")
print(f"важелі: чек треба {fmt_int(req_aov)} ₴ (×{TARGET_MODEL['levers']['aov']['ratio']}) при темпі {proj_orders} зам/міс · breakeven MER {BREAKEVEN_MER}" + (f" · MER {MER}" if MER else " · spend не підключено"))
print(f"facts={len(FACTS)} sku_facts={len(SKU_FACTS)} camp_facts={len(CAMP_FACTS)} canc_facts={len(CANC_FACTS)}")
