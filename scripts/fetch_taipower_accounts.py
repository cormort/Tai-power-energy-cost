"""抓政府資料開放平臺「台灣電力公司會計報表」(data.gov.tw/dataset/18917)，整理成 data/taipower_accounts.json。

ZIP 內每月有 IS（損益表）與 BS（資產負債表）XML，格式有兩種：
- GenericData：含科目名稱、層級、本月與累計數
- PBA_ROOT：只有科目代碼與本月數 → 名稱／層級沿用 GenericData 月份，累計數 = 上月累計 + 本月
"""
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://service.taipower.com.tw/data/opendata/apply/file/d018006/001.zip"
OUT = Path(__file__).resolve().parent.parent / "data" / "taipower_accounts.json"
KEY = {"41": "rev", "51": "cost", "510108": "thermal", "510111": "purchase", "64": "pretax", "68": "net"}


def tag(row, t):
    m = re.search(rf"<{re.escape(t)}>([^<]*)</{re.escape(t)}>", row)
    return m.group(1).strip() if m else None


def num(s):
    return float(s) if s not in (None, "") else None


def parse_xml(x):
    """回傳 (rows, names)：rows = {代碼: {...數值}}；names = {代碼: (名稱, 層級, 粗體, 序號)}（僅 GenericData 有）。"""
    rows, names = {}, {}
    for i, r in enumerate(re.findall(r"<ROW>(.*?)</ROW>", x, re.S)):
        code = tag(r, "編號") or tag(r, "科目編號") or tag(r, "會計科目")
        rows[code] = {
            "mA": num(tag(r, "本月份實際數")), "mB": num(tag(r, "本月份預算數")),
            "yA": num(tag(r, "本年度截至本月份實際數")), "yB": num(tag(r, "本年度截至本月份預算數")),
            "ann": num(tag(r, "本年度法定預算數")), "amt": num(tag(r, "金額")),
        }
        if tag(r, "科目"):
            names[code] = (tag(r, "科目"), int(tag(r, "LEVEL")), tag(r, "BOLD") == "1", i)
    return rows, names


def build(files):
    """files = {'11509IS': xml, ...} → 輸出 dict。"""
    names = {"IS": {}, "BS": {}}
    is_by_month, bs_by_month = {}, {}
    for key in sorted(files):
        ym, kind = key[:5], key[5:]
        rows, nm = parse_xml(files[key])
        names[kind].update(nm)
        (is_by_month if kind == "IS" else bs_by_month)[ym] = rows
    prev = {}
    for ym in sorted(is_by_month):
        rows = is_by_month[ym]
        for code, v in rows.items():
            p = prev.get(code, {}) if ym[3:] != "01" else {}
            if v["yA"] is None and v["mA"] is not None:
                v["yA"] = (p.get("yA") or 0) + v["mA"]
            if v["yB"] is None and v["mB"] is not None:
                v["yB"] = (p.get("yB") or 0) + v["mB"]
        prev = rows
    latest = max(is_by_month)
    bs_latest = max(bs_by_month)
    e8 = lambda v: None if v is None else round(v / 1e8, 2)
    order = lambda kind: sorted(names[kind], key=lambda c: names[kind][c][3])
    is_rows = [{"code": c, "name": names["IS"][c][0], "lv": names["IS"][c][1], "bold": names["IS"][c][2],
                **{k: e8(is_by_month[latest][c][k]) for k in ("mA", "mB", "yA", "yB", "ann")}}
               for c in order("IS") if c in is_by_month[latest]]
    bs_rows = [{"code": c, "name": names["BS"][c][0], "lv": names["BS"][c][1], "bold": names["BS"][c][2],
                "amt": e8(bs_by_month[bs_latest][c]["amt"])}
               for c in order("BS") if c in bs_by_month[bs_latest]]
    monthly = [{"ym": ym, **{f"{n}A": e8(is_by_month[ym].get(c, {}).get("mA")) for c, n in KEY.items()},
                **{f"{n}B": e8(is_by_month[ym].get(c, {}).get("mB")) for c, n in KEY.items()}}
               for ym in sorted(is_by_month)]
    return {"source": "https://data.gov.tw/dataset/18917", "latest": latest, "bs_date": bs_latest,
            "is": is_rows, "bs": bs_rows, "monthly": monthly}


def main():
    z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(URL, timeout=120).read()))
    files = {m.group(1): z.read(n).decode("utf-8") for n in z.namelist() if (m := re.fullmatch(r"(\d{5}(?:IS|BS))\.xml", n))}
    data = build(files)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("},{", "},\n{") + "\n")
    pt = next(r for r in data["is"] if r["code"] == "64")
    print(data["latest"], "稅前累計", pt["yA"], "預算", pt["yB"], "BS", data["bs_date"], len(data["bs"]))


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        gen = ("<GenericData><ROW><SEQNO>1</SEQNO><LEVEL>2</LEVEL><BOLD>1</BOLD><編號>64</編號><科目>稅前淨利（淨損）</科目>"
               "<本年度法定預算數>-300</本年度法定預算數><本月份實際數>-10</本月份實際數><本月份預算數>-20</本月份預算數>"
               "<本年度截至本月份實際數>-100</本年度截至本月份實際數><本年度截至本月份預算數>-200</本年度截至本月份預算數></ROW></GenericData>")
        pba = "<PBA_ROOT><ROW><會計科目>64</會計科目><本月份預算數>-5</本月份預算數><本年度法定預算數>-300</本年度法定預算數><本月份實際數>7</本月份實際數></ROW><ROW><會計科目>99</會計科目><本月份實際數>1</本月份實際數></ROW></PBA_ROOT>"
        bsg = "<GenericData><ROW><SEQNO>1</SEQNO><LEVEL>01</LEVEL><BOLD>1</BOLD><科目>資產</科目><金額>500</金額><科目編號>1</科目編號></ROW></GenericData>"
        d = build({"11509IS": gen, "11510IS": pba, "11509BS": bsg})
        r = d["is"][0]
        assert d["latest"] == "11510" and r["name"] == "稅前淨利（淨損）" and len(d["is"]) == 1
        assert (r["yA"], r["yB"], r["mA"]) == (round(-93 / 1e8, 2), round(-205 / 1e8, 2), round(7 / 1e8, 2))
        assert d["monthly"][1]["pretaxA"] == round(7 / 1e8, 2) and d["bs"][0]["name"] == "資產"
        print("ok")
    else:
        main()
