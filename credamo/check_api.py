import sys, requests
sys.path.insert(0, ".")

from browser import launch_browser, get_cookies, find_survey_id_via_cdp

config = {}
try:
    from config import load_config
    config = load_config()
except:
    pass

cdp_port = config.get("cdp_port", 9222)
survey_id, _, _ = find_survey_id_via_cdp(cdp_port)

try:
    p, browser, context, page, _ = launch_browser()
except:
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
    context = browser.contexts[0]
    page = context.pages[0]

cookie_str = get_cookies(context)
headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "referer": f"https://www.credamo.com/survey.html?surveyId={survey_id}",
    "cookie": cookie_str,
    "content-type": "application/json"
}

# Test different page sizes and check total
for ps in [10, 20, 50]:
    r = requests.post(
        "https://www.credamo.com/v1/cleanVar/dataOverview",
        headers=headers,
        params={"currPageSize": ps, "currPageIndex": 1},
        json={"surveyId": survey_id},
        timeout=30,
        verify=False
    )
    if r.status_code == 200:
        resp = r.json()
        if resp.get("success") and resp.get("data"):
            total = resp["data"].get("total", 0)
            rows = resp["data"].get("rowList", [])
            print(f"page_size={ps}: returned {len(rows)} rows, total={total}")

# Now also check the old API endpoint
for ps in [10]:
    url = f"https://www.credamo.com/v1/cleanVar/qstOverviewBySurId/{survey_id}?currPageSize={ps}&currPageIndex=1"
    r2 = requests.get(url=url, headers={"user-agent": "Mozilla/5.0", "cookie": cookie_str}, timeout=30, verify=False)
    if r2.status_code == 200:
        try:
            resp2 = r2.json()
            print(f"\nOld API (qstOverviewBySurId): {resp2.get('total', '?')} total")
            if resp2.get('data') and resp2['data'].get('rowList'):
                for i, row in enumerate(resp2['data']['rowList'][:3]):
                    print(f"  row {i+1}: userId={row.get('userId')}, status={row.get('status')}")
        except:
            print(f"Old API returned non-JSON: {r2.text[:200]}")
    else:
        print(f"\nOld API HTTP {r2.status_code}")

browser.close()
p.stop()
