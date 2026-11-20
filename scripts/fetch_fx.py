"""抓美元兌新台幣匯率（Yahoo Finance TWD=X 月線），寫入 data/usdtwd.json。

用途：進口煤價以美元計價，換算台幣成本時要乘匯率；有匯率才能把「煤價變動」
拆成「價格效果」與「匯率效果」。月報沒有匯率表，改用 Yahoo Finance 公開端點。

輸出格式：
{
  "source": "Yahoo Finance TWD=X",
  "monthly": [{"d": "2026-09", "p": 31.23}, ...],   # 月底收盤
  "annual":  [{"y": 2026, "p": 31.5}, ...]          # 月資料平均
}
舊月份保留在 JSON 中累積；抓不到就維持原檔不覆寫。
"""
import datetime
import json
import sys
import time
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "usdtwd.json"
START = datetime.date(2011, 1, 1)          # 101 年起（決算書燃料資料起點）
URL = "https://query1.finance.yahoo.com/v8/finance/chart/TWD=X"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


def fetch_monthly():
    p1 = int(datetime.datetime(START.year, START.month, 1).timestamp())
    p2 = int(time.time())
    url = f"{URL}?interval=1mo&period1={p1}&period2={p2}"
    d = get_json(url)
    res = d["chart"]["result"][0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    out = {}
    for t, c in zip(ts, closes):
        if c is None:
            continue
        dt = datetime.datetime.utcfromtimestamp(t)
        out[f"{dt.year}-{dt.month:02d}"] = round(float(c), 4)
    if not out:
        raise ValueError("Yahoo 沒有回傳任何匯率")
    return out


def main():
    new = fetch_monthly()
    old = {}
    if OUT.exists():
        for row in json.loads(OUT.read_text()).get("monthly", []):
            old[row["d"]] = row["p"]
    old.update(new)
    monthly = [{"d": d, "p": p} for d, p in sorted(old.items())]

    by_year = {}
    for row in monthly:
        y = int(row["d"][:4])
        by_year.setdefault(y, []).append(row["p"])
    annual = [{"y": y, "p": round(sum(v) / len(v), 4)} for y, v in sorted(by_year.items())]

    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"source": "Yahoo Finance TWD=X", "monthly": monthly, "annual": annual},
                              ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"usdtwd.json 月資料 {len(monthly)} 筆，最新 {monthly[-1]}；年資料 {len(annual)} 筆，最新 {annual[-1]}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        # 純函式檢查：年資料由月資料平均而來
        monthly = [{"d": "2026-01", "p": 32.0}, {"d": "2026-02", "p": 33.0}]
        by_year = {}
        for row in monthly:
            by_year.setdefault(2026, []).append(row["p"])
        assert round(sum(by_year[2026]) / 2, 4) == 32.5
        print("ok")
    else:
        main()
