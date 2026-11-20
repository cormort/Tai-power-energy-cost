"""抓中油天然氣牌價（102F 0100400 天然氣（2）電業用戶），依實施日期月份寫入 data/cpc_gas.json。"""
import json
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://vipmbr.cpc.com.tw/mbwebs/showlistprice.aspx?prodtype=8"
OUT = Path(__file__).resolve().parent.parent / "data" / "cpc_gas.json"


def parse(html):
    date = re.search(r"實施日期[:：]\s*(\d{4})/(\d{2})/(\d{2})", html)
    if not date:
        raise ValueError("找不到實施日期")
    rows = {}
    for ctl, field, val in re.findall(r'id="MyGridView_(ctl\d+)_Label_([^"]+)">([^<]*)<', html):
        rows.setdefault(ctl, {})[field] = val.strip()
    hits = [r for r in rows.values()
            if r.get("產品編號") == "102F 0100400" and r.get("銷售對象") == "電業用戶"]
    if len(hits) != 1:
        raise ValueError(f"電業用戶列數異常：{len(hits)}")
    y, m, d = date.groups()
    return {"d": f"{y}-{m}", "p": float(hits[0]["參考牌價"]), "eff": f"{y}-{m}-{d}"}


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    row = parse(html)
    data = json.loads(OUT.read_text()) if OUT.exists() else []
    data = [x for x in data if x["d"] != row["d"]] + [row]
    data.sort(key=lambda x: x["d"])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(row)


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        sample = ('<span id="Label_Date"><br>實施日期:2026/11/01</span>'
                  '<span id="MyGridView_ctl06_Label_產品編號">102F 0100400</span>'
                  '<span id="MyGridView_ctl06_Label_銷售對象">工業用戶</span>'
                  '<span id="MyGridView_ctl06_Label_參考牌價">16.5251</span>'
                  '<span id="MyGridView_ctl09_Label_產品編號">102F 0100400</span>'
                  '<span id="MyGridView_ctl09_Label_銷售對象">電業用戶</span>'
                  '<span id="MyGridView_ctl09_Label_參考牌價">25.9059</span>')
        assert parse(sample) == {"d": "2026-11", "p": 25.9059, "eff": "2026-11-01"}
        print("ok")
    else:
        main()
