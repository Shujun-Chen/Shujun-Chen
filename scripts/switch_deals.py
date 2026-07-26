import requests, json, os
from datetime import datetime

REGIONS = {
    "JP": {"name": "日服", "currency": "¥"},
    "US": {"name": "美服", "currency": "$"},
    "HK": {"name": "港服", "currency": "HK$"},
}

ALGOLIA_APP_ID = "U3B6GR4UA3"
ALGOLIA_API_KEY = "a29c6927638bfd8cee23993e51e721c9"
ALGOLIA_INDEX = "ncom_game_en_us"

def fetch_us_sales(limit=30):
    url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/queries"
    h = {"X-Algolia-Application-Id": ALGOLIA_APP_ID, "X-Algolia-API-Key": ALGOLIA_API_KEY}
    payload = {"requests": [{"indexName": ALGOLIA_INDEX, "query": "", "params": f"hitsPerPage={limit}&filters=salePrice<msrp AND salePrice>0"}]}
    resp = requests.post(url, json=payload, headers=h, timeout=15)
    data = resp.json()
    games = []
    for hit in data.get("results", [{}])[0].get("hits", []):
        pct = round((1 - hit["salePrice"] / hit["msrp"]) * 100)
        if pct >= 20:
            games.append({"title": hit["title"], "msrp": hit["msrp"], "sale_price": hit["salePrice"], "discount_pct": pct, "currency": "$", "region": "US"})
    return games

def fetch_jp_sales(limit=30):
    url = "https://search.nintendo.jp/ncom_0001/sale.json"
    p = {"opt_hard": "1_HAC", "opt_ss": "store_on_sale", "limit": limit, "offset": 0}
    games = []
    try:
        resp = requests.get(url, params=p, headers={"Accept-Language": "ja"}, timeout=15)
        data = resp.json()
        for item in data.get("result", {}).get("items", []):
            t = item.get("title", "")
            pr = item.get("price", {})
            reg = pr.get("regular", {}).get("amount", 0)
            sale = pr.get("sale", {}).get("amount", 0)
            if sale > 0 and reg > 0:
                pct = round((1 - sale / reg) * 100)
                if pct >= 20:
                    games.append({"title": t, "msrp": reg, "sale_price": sale, "discount_pct": pct, "currency": "¥", "region": "JP"})
    except Exception as e:
        print(f"JP error: {e}")
    return games

def fetch_hk_sales(limit=30):
    games = []
    try:
        resp = requests.get("https://store.nintendo.com.hk/api/game/category/onsale", params={"limit": limit, "offset": 0}, headers={"Accept-Language": "zh-Hant"}, timeout=15)
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        for item in items:
            t = item.get("title", "") or item.get("name", "")
            pr = float(item.get("price", 0) or item.get("regular_price", 0))
            sale = float(item.get("sale_price", 0) or item.get("current_price", 0))
            if sale > 0 and pr > 0:
                pct = round((1 - sale / pr) * 100)
                if pct >= 20:
                    games.append({"title": t, "msrp": pr, "sale_price": sale, "discount_pct": pct, "currency": "HK$", "region": "HK"})
    except Exception as e:
        print(f"HK error: {e}")
    return games

def find_cross_region(all_games):
    by_title = {}
    for g in all_games:
        key = g["title"].lower().strip()
        by_title.setdefault(key, []).append(g)
    cross = []
    for title, entries in by_title.items():
        if len(entries) >= 2:
            cheapest = min(entries, key=lambda x: x["sale_price"])
            entries.sort(key=lambda x: x["discount_pct"], reverse=True)
            cross.append({"title": entries[0]["title"], "regions": entries, "cheapest": REGIONS[cheapest["region"]]["name"]})
    cross.sort(key=lambda x: x["regions"][0]["discount_pct"], reverse=True)
    return cross

def format_post(all_games, cross_deals):
    now = datetime.now().strftime("%Y-%m-%d")
    lines = [f"Switch折扣精选 {now}", ""]
    if cross_deals:
        lines.append("多区比价(标*为最便宜区):")
        for deal in cross_deals[:5]:
            best = [r for r in deal["regions"] if REGIONS[r["region"]]["name"] == deal["cheapest"]][0]
            lines.append(f"\n{deal['title']}")
            for r in deal["regions"]:
                star = " *" if r == best else ""
                c = REGIONS[r["region"]]["currency"]
                lines.append(f"  {c}{r['sale_price']:.0f} (-{r['discount_pct']}%){star}")
    lines.append("")
    flags = {"JP":"日服", "US":"美服", "HK":"港服"}
    for rk, ri in REGIONS.items():
        rg = [g for g in all_games if g["region"] == rk]
        rg.sort(key=lambda x: x["discount_pct"], reverse=True)
        if rg:
            lines.append(f"\n{flags[rk]}:")
            for g in rg[:3]:
                lines.append(f"  {g['title'][:20]} {g['currency']}{g['sale_price']:.0f} (-{g['discount_pct']}%)")
    lines.append("\n#Switch #Switch折扣 #任天堂")
    return "\n".join(lines)

# === MAIN ===
print("Fetching Switch deals...")
all_games = []
for label, fn in [("US", fetch_us_sales), ("JP", fetch_jp_sales), ("HK", fetch_hk_sales)]:
    print(f"  {label}...")
    result = fn(30)
    all_games.extend(result)
    print(f"    {len(result)} deals")

print(f"\nTotal: {len(all_games)} deals")
cross = find_cross_region(all_games)
print(f"Cross-region: {len(cross)} games")

post = format_post(all_games, cross)
print("\n" + "="*40)
print(post)
print("="*40)

outdir = os.path.expanduser("~/存储/cloud_sync/02_work/工作文档/")
os.makedirs(outdir, exist_ok=True)
path = os.path.join(outdir, f"switch_deals_{datetime.now().strftime('%Y%m%d')}.txt")
with open(path, "w") as f:
    f.write(post)
print(f"\nSaved: {path}")
