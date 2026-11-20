"""抓能源署「發電燃料耗用」台電進口液化天然氣逐月用量（千立方公尺），寫入 data/taipower_gas_monthly.json。"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = "https://ea01.moeaea.gov.tw/a0303/02/api/v1/electric-fuel-consumption"
OUT = Path(__file__).resolve().parent.parent / "data" / "taipower_gas_monthly.json"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


def parse(resp):
    cols = {c["name"]: c for c in resp["data"]}
    dates, qty = cols["日期"]["values"], cols["台電-進口液化天然氣"]
    assert qty["unit"] == "千立方公尺", qty["unit"]
    return [{"d": "%d-%s" % (int(s[:3]) + 1911, s[4:6]), "q": round(v)} for s, v in zip(dates, qty["values"])]


def main():
    mx = get(BASE + "/opts")["minMaxRange"]["max"]  # 例 11509 = 115 年 9 月
    url = f"{BASE}?period=m&start_y=112&start_m=1&end_y={mx // 100}&end_m={mx % 100}&unit=0&selection1=t&selection2=3100"
    rows = parse(get(url))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rows, separators=(",", ":")).replace("},{", "},\n{") + "\n")
    print(len(rows), rows[-1])


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        resp = {"data": [{"name": "日期", "values": ["114年12月", "115年01月"]},
                         {"name": "台電-進口液化天然氣", "unit": "千立方公尺", "values": [1418000.4, 1450856.606]}]}
        assert parse(resp) == [{"d": "2025-12", "q": 1418000}, {"d": "2026-01", "q": 1450857}]
        print("ok")
    else:
        main()
