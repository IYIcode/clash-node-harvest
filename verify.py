"""端到端验收：把订阅原样（含 dns / GEOIP 规则 / 分组）交给 mihomo 内核，
选中 🚀 自动选择 后逐个真打外网请求，证明"这份订阅能用"而不是"探测数字好看"。

用法: python verify.py [订阅路径] [测几个节点]
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

KERNEL = r"C:\Program Files\Clash Verge\verge-mihomo.exe"
MIXED, CTL = 17890, 17891
API = f"http://127.0.0.1:{CTL}"
AUTO_GROUP = "🚀 自动选择"
TARGETS = ("https://www.cloudflare.com/cdn-cgi/trace", "https://www.google.com/generate_204")

src = Path(sys.argv[1] if len(sys.argv) > 1 else "output/clash.yaml")
n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
d = src.parent / ".verify"
d.mkdir(parents=True, exist_ok=True)

cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
cfg.update({"mixed-port": MIXED, "external-controller": f"127.0.0.1:{CTL}", "secret": "",
            "mode": "global", "geodata-mode": True})
# 内核默认去找 geoip.metadb（要连 GitHub 下载，国内直连基本不通，配置会加载失败）。
# 本机跑就借 Clash Verge 已经下好的 geo 库，走 .dat 格式。
for geo in (Path(r"C:\Users\IYI\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev"), Path.home()):
    if (geo / "geoip.dat").exists():
        for f in ("geoip.dat", "geosite.dat", "Country.mmdb"):
            if (geo / f).exists():
                shutil.copyfile(geo / f, d / f)
        break

run = d / "run.yaml"
run.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
chk = subprocess.run([KERNEL, "-t", "-d", str(d), "-f", str(run)], capture_output=True, text=True)
print("订阅原样加载:", "通过" if chk.returncode == 0 else "失败")
if chk.returncode:
    print((chk.stderr or chk.stdout)[-600:])
    sys.exit(1)

log = open(d / "kernel.log", "w", encoding="utf-8", errors="replace")
proc = subprocess.Popen([KERNEL, "-d", str(d), "-f", str(run)], stdout=log, stderr=log, stdin=subprocess.DEVNULL)
proxies = {"http": f"http://127.0.0.1:{MIXED}", "https": f"http://127.0.0.1:{MIXED}"}
try:
    for _ in range(60):
        if proc.poll() is not None:
            print("内核启动失败:\n" + (d / "kernel.log").read_text(encoding="utf-8", errors="replace")[-1200:])
            sys.exit(1)
        try:
            if requests.get(API + "/version", timeout=2).ok:
                break
        except Exception:
            pass
        time.sleep(0.5)

    requests.put(API + "/proxies/GLOBAL", json={"name": AUTO_GROUP}, timeout=5)
    now = None
    for _ in range(30):  # 等首轮 url-test 探完并选中一个（history 只留最近几条，别拿它当收敛条件）
        g = requests.get(API + f"/proxies/{quote(AUTO_GROUP)}", timeout=5).json()
        now = g.get("now")
        if now and now != "DIRECT":
            break
        time.sleep(2)
    print(f"{len(cfg['proxies'])} 个节点，自动选择组当前命中: {now or '（未收敛）'}")

    names = [p["name"] for p in cfg["proxies"]]
    tested = ([now] if now else []) + [x for x in names if x != now][: n - 1]
    ok = 0
    for name in tested:
        requests.put(API + "/proxies/GLOBAL", json={"name": name}, timeout=5)
        time.sleep(1)  # 切换选路后马上发请求会误判，内核要重开隧道
        try:
            r = requests.get(TARGETS[0], proxies=proxies, timeout=12)
            exit_ip = [l for l in r.text.splitlines() if l.startswith("ip=")]
            g = requests.get(TARGETS[1], proxies=proxies, timeout=12)
            print(f"  {name[:44]:46s} -> HTTP {r.status_code} 出口 {exit_ip}  Google {g.status_code}")
            ok += 1
        except Exception as e:
            print(f"  {name[:44]:46s} -> 失败 {type(e).__name__}: {str(e.__cause__ or e)[:70]}")
    print(f"实测出网成功 {ok}/{len(tested)}")
finally:
    proc.terminate()
    log.close()
