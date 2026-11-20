"""抓能源署「發電燃料耗用」台電逐月用量，寫入 data/：
- taipower_gas_monthly.json：進口液化天然氣（千立方公尺）
- taipower_coal_monthly.json：煙煤-燃料煤 + 亞煙煤（公噸）
- taipower_fuel_oil_monthly.json / taipower_diesel_monthly.json：燃料油／柴油（公秉）
"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = "https://ea01.moeaea.gov.tw/a0303/02/api/v1/electric-fuel-consumption"
DATA = Path(__file__).resolve().parent.parent / "data"
# 輸出檔 → (selection2 代碼, 欄位名稱, 單位)
SERIES = {
    "taipower_gas_monthly.json": ("3100", ["台電-進口液化天然氣"], "千立方公尺"),
    "taipower_coal_monthly.json": ("1a20,1a40", ["台電-煙煤-燃料煤", "台電-亞煙煤"], "公噸"),
    "taipower_fuel_oil_monthly.json": ("2110", ["台電-燃料油"], "公秉"),
    "taipower_diesel_monthly.json": ("2100", ["台電-柴油"], "公秉"),
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


def parse(resp, names, unit):
    cols = {c["name"]: c for c in resp["data"]}
    for n in names:
        assert cols[n]["unit"] == unit, (n, cols[n]["unit"])
    dates = cols["日期"]["values"]
    return [{"d": "%d-%s" % (int(s[:3]) + 1911, s[4:6]), "q": round(sum(cols[n]["values"][i] for n in names))}
            for i, s in enumerate(dates)]


def main():
    mx = get(BASE + "/opts")["minMaxRange"]["max"]  # 例 11509 = 115 年 9 月
    for fname, (codes, names, unit) in SERIES.items():
        url = (f"{BASE}?period=m&start_y=112&start_m=1&end_y={mx // 100}&end_m={mx % 100}"
               f"&unit=0&selection1=t&selection2={codes.replace(',', '%2C')}")
        rows = parse(get(url), names, unit)
        DATA.mkdir(exist_ok=True)
        (DATA / fname).write_text(json.dumps(rows, separators=(",", ":")).replace("},{", "},\n{") + "\n")
        print(fname, len(rows), rows[-1])


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        resp = {"data": [{"name": "日期", "values": ["114年12月", "115年01月"]},
                         {"name": "台電-煙煤-燃料煤", "unit": "公噸", "values": [1000.4, 2000]},
                         {"name": "台電-亞煙煤", "unit": "公噸", "values": [500, 0.2]}]}
        assert parse(resp, ["台電-煙煤-燃料煤", "台電-亞煙煤"], "公噸") == [
            {"d": "2025-12", "q": 1500}, {"d": "2026-01", "q": 2000}]
        print("ok")
    else:
        main()
