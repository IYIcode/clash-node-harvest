"""把生成的 clash.yaml 当真实配置启动内核，验证能否通过代理访问境外站点。"""
import subprocess
import sys
import time
from pathlib import Path

import requests
import yaml

KERNEL = sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files\Clash Verge\verge-mihomo.exe"
d = Path("output/.verify")
d.mkdir(parents=True, exist_ok=True)
cfg = yaml.safe_load(Path("output/clash.yaml").read_text(encoding="utf-8"))
cfg["mixed-port"] = 17890
cfg["external-controller"] = "127.0.0.1:17891"
cfg["secret"] = ""
cfg["mode"] = "global"
cfg.pop("rules", None)
p = d / "run.yaml"
p.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
log = open(d / "run.log", "w", encoding="utf-8", errors="replace")
proc = subprocess.Popen([KERNEL, "-d", str(d), "-f", str(p)], stdout=log, stderr=log, stdin=subprocess.DEVNULL)
proxies = {"http": "http://127.0.0.1:17890", "https": "http://127.0.0.1:17890"}
try:
    for _ in range(60):
        if proc.poll() is not None:
            print("内核启动失败:\n" + Path(d / "run.log").read_text(encoding="utf-8", errors="replace")[-1500:])
            sys.exit(1)
        try:
            if requests.get("http://127.0.0.1:17891/version", timeout=2).ok:
                break
        except Exception:
            pass
        time.sleep(0.5)
    requests.put("http://127.0.0.1:17891/proxies/GLOBAL", json={"name": "🚀 自动选择"}, timeout=5)
    hit = None
    for i in range(40):  # 等 url-test 组跑完首轮全量测速（lazy:false 时会逐个探测）
        try:
            g = requests.get("http://127.0.0.1:17891/proxies", timeout=5).json()["proxies"].get("🚀 自动选择", {})
            hist = g.get("history") or []
            if len(hist) >= max(3, len(g.get("all", [])) // 2):
                hit = (g.get("now"), hist[0].get("delay"), len(hist))
                break
        except Exception:
            pass
        time.sleep(3)
    print(f"首轮测速: 已探测 {hit[2] if hit else 0} 个节点，命中 {hit[0] if hit else '（未收敛）'} "
          f"{hit[1] if hit else ''}ms")
    for target in ("http://www.gstatic.com/generate_204", "https://www.google.com/", "https://api.ip.sb/ipinfo"):
        try:
            r = requests.get(target, proxies=proxies, timeout=20)
            body = r.text[:120].replace("\n", " ")
            print(f"  {target} -> HTTP {r.status_code}  {body}")
        except Exception as e:
            print(f"  {target} -> 失败 {type(e).__name__}: {str(e)[:90]}")
finally:
    proc.terminate()
    try:
        proc.wait(5)
    except Exception:
        proc.kill()
