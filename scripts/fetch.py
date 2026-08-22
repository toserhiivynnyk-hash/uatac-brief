# -*- coding: utf-8 -*-
"""UATAC — фетч сирих даних KeyCRM (READ-ONLY). Пише /home/claude/keycrm_raw.json"""
import urllib.request, json, time, datetime, os, sys

TOKEN = os.environ.get("KEYCRM_TOKEN", "").strip()
if not TOKEN:
    sys.exit("НЕМАЄ KEYCRM_TOKEN. Додай його в Settings → Secrets and variables → Actions → New repository secret.")
BASE = "https://openapi.keycrm.app/v1"
RAW_PATH = os.environ.get("UATAC_RAW", "/home/claude/keycrm_raw.json")
os.makedirs(os.path.dirname(RAW_PATH) or ".", exist_ok=True)

def get(url, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN, "Accept": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:
            if i == retries - 1: raise
            time.sleep(2 + i)

def fetch_pages(path, params="", max_pages=200):
    out = []
    for page in range(1, max_pages + 1):
        url = f"{BASE}/{path}?limit=50&page={page}" + (("&" + params) if params else "")
        d = get(url)
        items = d.get("data", []) if isinstance(d, dict) else d
        if not items: break
        out.extend(items)
        if len(items) < 50: break
        time.sleep(0.4)
    return out

DAYS = 125
if "--days" in sys.argv: DAYS = int(sys.argv[sys.argv.index("--days") + 1])
today = datetime.date.today()
start = today - datetime.timedelta(days=DAYS)
df = urllib.request.quote(f"filter[created_between]={start} 00:00:00,{today} 23:59:59", safe="=&[],").replace(" ", "%20")

print(f"fetch {start} -> {today}", flush=True)
statuses = fetch_pages("order/status")
print("statuses", len(statuses), flush=True)
sources = fetch_pages("order/source")
print("sources", len(sources), flush=True)
orders = fetch_pages("order", f"include=marketing,products&sort=-id&{df}")
print("orders", len(orders), flush=True)
offers = fetch_pages("offers", "include=product")
print("offers", len(offers), flush=True)

json.dump({"statuses": statuses, "sources": sources, "orders": orders, "offers": offers,
           "fetched_at": datetime.datetime.now().isoformat(),
           "period_start": str(start), "period_end": str(today)},
          open(RAW_PATH, "w"), ensure_ascii=False)
print("DONE", RAW_PATH, flush=True)
