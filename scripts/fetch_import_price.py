"""抓能源署月報「9-02 進口能源價格」煙煤-燃料煤 CIF（美元/公噸）逐月值，合併寫入 data/import_coal_price.json。
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
OUT = Path(__file__).resolve().parent.parent / "data" / "import_coal_price.json"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read()


def xlsx_rows(data):
    """回傳 [[(欄字母, 值), ...], ...]；只用標準函式庫讀 sheet1。"""
    z = zipfile.ZipFile(io.BytesIO(data))
    ss = [re.sub(r"<[^>]+>", "", s) for s in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), re.S)]
    rows = []
    for r in re.findall(r"<row[^>]*>(.*?)</row>", z.read("xl/worksheets/sheet1.xml").decode(), re.S):
        cells = []
        for ref, attrs, v in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(?:<f>.*?</f>)?<v>([^<]*)</v>', r, re.S):
            cells.append((ref, ss[int(v)] if 't="s"' in attrs else v))
        rows.append(cells)
    return rows


def parse(rows):
    col = next(c for r in rows for c, v in r if "燃料煤" in v and "CIF" in v)
    out = {}
    for r in rows:
        d = dict(r)
        period = next((v for v in d.values() if re.fullmatch(r"\d{4}/\d{2}", v)), None)
        if period and col in d:
            out[period.replace("/", "-")] = round(float(d[col]), 4)
    if not out:
        raise ValueError("找不到燃料煤逐月價格")
    return out


def main():
    page = get(ROOT + "/api/pages/newest/monthly").decode("utf-8")
    path = re.search(r"/api/files/m_9-02[^\"]*?\.xlsx", page).group(0)
    new = parse(xlsx_rows(get(ROOT + urllib.parse.quote(path))))
    old = {x["d"]: x["p"] for x in json.loads(OUT.read_text())} if OUT.exists() else {}
    old.update(new)
    rows = [{"d": d, "p": p} for d, p in sorted(old.items())]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rows, separators=(",", ":")).replace("},{", "},\n{") + "\n")
    print(path, len(rows), rows[-1])


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        rows = [[("A", "期間"), ("E", "煙煤-燃料煤\n(美元/公噸：CIF)")],
                [("A", "114年"), ("E", "114.77"), ("F", "2025")],
                [("A", "09月"), ("C", "880.6"), ("E", "139.05266"), ("F", "2026/09")]]
        assert parse(rows) == {"2026-09": 139.0527}
        print("ok")
    else:
        main()
