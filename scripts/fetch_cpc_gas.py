"""抓中油天然氣歷史價格（102F 0100400 電業用戶），展開成逐月牌價寫入 data/cpc_gas.json。"""
import datetime
import json
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://vipmbr.cpc.com.tw/mbwebs/showhistoryprice_8.aspx"
OUT = Path(__file__).resolve().parent.parent / "data" / "cpc_gas.json"


def parse(html):
    """回傳 {(y, m, d): 電業用戶牌價}；早年分季時取「電業用戶其他月」。"""
    adj = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        c = [re.sub(r"<[^>]+>|&nbsp;", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(c) > 10 and c[1] == "102F 0100400" and (c[6] or c[10]):
            y, m, d = map(int, c[0].split("/"))
            adj[(y, m, d)] = float(c[6] or c[10])
    if not adj:
        raise ValueError("找不到電業用戶牌價")
    return adj


def monthly(adj, until):
    """每月取當月（含）以前最近一次調價；until = (y, m)。"""
    ds = sorted(adj)
    out, i, cur = [], 0, None
    y, m = ds[0][0], ds[0][1]
    while (y, m) <= until:
        while i < len(ds) and ds[i][:2] <= (y, m):
            cur = ds[i]
            i += 1
        out.append({"d": f"{y}-{m:02d}", "p": adj[cur], "eff": "%d-%02d-%02d" % cur})
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    adj = parse(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    # 當月未調價時歷史表不會新增列，仍延伸到本月（沿用上次牌價）
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    rows = monthly(adj, max(max(adj)[:2], (now.year, now.month)))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("},{", "},\n{") + "\n")
    print(len(rows), rows[-1])


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        row = lambda d, code, p6, p10: (f"<tr><td>{d}</td><td>{code}</td>" + "<td>1</td>" * 4
                                        + f"<td>{p6}</td><td></td><td></td><td></td><td>{p10}</td><td></td></tr>")
        sample = (row("2026/11/1", "102F 0100400", "25.9059", "") + row("2026/11/1", "102F 0100100", "9", "")
                  + row("2009/7/7", "102F 0100400", "", "14.2787") + row("2009/1/1", "102F 0100400", "", "13.1873"))
        adj = parse(sample)
        assert adj == {(2026, 11, 1): 25.9059, (2009, 7, 7): 14.2787, (2009, 1, 1): 13.1873}
        s = {r["d"]: r for r in monthly(adj, (2026, 12))}
        assert s["2009-06"]["p"] == 13.1873 and s["2009-07"]["p"] == 14.2787
        assert s["2026-10"]["p"] == 14.2787 and s["2026-12"] == {"d": "2026-12", "p": 25.9059, "eff": "2026-11-01"}
        print("ok")
    else:
        main()
