"""抓能源署能源統計月報價格表逐月值，合併寫入 data/：
- 9-02 進口能源價格：煙煤-燃料煤 CIF（美元/公噸）→ import_coal_price.json
- 9-01 國內能源價格（油品）：低硫燃料油 S0.5%（元/公秉，含稅）→ fuel_oil_price.json
                              超級/高級柴油（元/公升，含稅）→ diesel_price.json
月報只含近兩年月資料，舊月份保留在 JSON 中累積。"""
import io
import json
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = "https://ea01.moeaea.gov.tw/a0303/02"
DATA = Path(__file__).resolve().parent.parent / "data"
# (月報表號, 工作表, 欄名判斷, 輸出檔)
SERIES = [
    ("9-02", 1, lambda v: "燃料煤" in v and "CIF" in v, "import_coal_price.json"),
    ("9-01", 1, lambda v: v.startswith("低硫燃料油(S:0.5%)"), "fuel_oil_price.json"),
    ("9-01", 1, lambda v: "柴油" in v and "公升" in v, "diesel_price.json"),
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read()


def xlsx_rows(data, sheet):
    """回傳 [[(欄字母, 值), ...], ...]；只用標準函式庫讀指定工作表。"""
    z = zipfile.ZipFile(io.BytesIO(data))
    ss = [re.sub(r"<[^>]+>", "", s) for s in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), re.S)]
    rows = []
    for r in re.findall(r"<row[^>]*>(.*?)</row>", z.read(f"xl/worksheets/sheet{sheet}.xml").decode(), re.S):
        cells = []
        for ref, attrs, v in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(?:<f>.*?</f>)?<v>([^<]*)</v>', r, re.S):
            cells.append((ref, ss[int(v)] if 't="s"' in attrs else v))
        rows.append(cells)
    return rows


def parse(rows, match):
    col = next(c for r in rows for c, v in r if match(v))
    out = {}
    for r in rows:
        d = dict(r)
        period = next((v for v in d.values() if re.fullmatch(r"\d{4}/\d{2}", v)), None)
        if period and col in d and float(d[col]):
            out[period.replace("/", "-")] = round(float(d[col]), 4)
    if not out:
        raise ValueError("找不到逐月價格")
    return out


def main():
    page = get(ROOT + "/api/pages/newest/monthly").decode("utf-8")
    files = {}
    for table, sheet, match, fname in SERIES:
        if table not in files:
            path = re.search(rf"/api/files/m_{table}[^\"]*?\.xlsx", page).group(0)
            files[table] = get(ROOT + urllib.parse.quote(path))
        new = parse(xlsx_rows(files[table], sheet), match)
        out = DATA / fname
        old = {x["d"]: x["p"] for x in json.loads(out.read_text())} if out.exists() else {}
        old.update(new)
        rows = [{"d": d, "p": p} for d, p in sorted(old.items())]
        DATA.mkdir(exist_ok=True)
        out.write_text(json.dumps(rows, separators=(",", ":")).replace("},{", "},\n{") + "\n")
        print(fname, len(rows), rows[-1])


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        rows = [[("A", "期間"), ("E", "煙煤-燃料煤\n(美元/公噸：CIF)"), ("G", "甲種低硫燃料油/\n低硫鍋爐用油(S:0.5%)"), ("H", "低硫燃料油(S:0.5%)\n(新臺幣元/公秉)")],
                [("A", "114年"), ("E", "114.77"), ("F", "2025")],
                [("A", "09月"), ("C", "880.6"), ("E", "139.05266"), ("G", "0.0"), ("H", "24658.0"), ("K", "2026/09")]]
        assert parse(rows, SERIES[0][2]) == {"2026-09": 139.0527}
        assert parse(rows, SERIES[1][2]) == {"2026-09": 24658.0}
        print("ok")
    else:
        main()
