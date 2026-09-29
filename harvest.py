"""采集公开免费节点源，测活淘汰，生成统一的 Clash(Mihomo) 订阅配置。"""

import argparse
import base64
import json
import os
import random
import re
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

import requests
import yaml

LINK_RE = re.compile(
    r"(?<![A-Za-z0-9+/.-])((?:ss|ssr|vmess|vless|trojan|hysteria2?|hy2|tuic|anytls)://[^\s'\"<>()\\]+)",
    re.IGNORECASE,
)
SUPPORTED_TYPES = {
    "ss", "vmess", "vless", "trojan", "hysteria", "hysteria2", "tuic",
    "anytls", "wireguard", "snell", "direct",
}
PROBE_URL = "http://www.gstatic.com/generate_204"
SPEED_URL = "https://speed.cloudflare.com/__down?bytes=2000000"
UA = "clash-verge/v2.0"

REGION_RULES = [
    ("美国", r"美国|美服|🇺🇸|\bUS[A-Z]?-\b|America|USA|Los.?Angeles|San.?Jose|Santa.?Clara|Miami|New.?York|Chicago|Oregon|Portland|Seattle|Ashburn|Dallas|Atlanta|St.?Louis"),
    ("日本", r"日本|日服|🇯🇵|\bJP\b|Japan|Tokyo|Osaka|Yokohama"),
    ("香港", r"香港|港服|🇭🇰|\bHK\b|Hong.?Kong"),
    ("台湾", r"台湾|台服|🇹🇼|\bTW\b|Taipei|Taiwan|Keelung"),
    ("新加坡", r"新加坡|🇸🇬|\bSG\b|Singapore"),
    ("韩国", r"韩国|🇰🇷|\bKR\b|Korea|Seoul"),
    ("英国", r"英国|🇬🇧|\bUK\b|GB\b|London|Britain"),
    ("德国", r"德国|🇩🇪|\bDE\b|Germany|Frankfurt|Dusseldorf|Berlin"),
    ("法国", r"法国|🇫🇷|\bFR\b|France|Paris"),
    ("加拿大", r"加拿大|🇨🇦|\bCA\b|Canada|Toronto|Montreal|Vancouver"),
    ("荷兰", r"荷兰|🇳🇱|\bNL\b|Netherlands|Amsterdam"),
    ("俄罗斯", r"俄罗斯|🇷🇺|\bRU\b|Russia|Moscow|Saint.?Petersburg"),
    ("澳大利亚", r"澳大利亚|澳洲|🇦🇺|\bAU\b|Australia|Sydney|Melbourne"),
    ("印度", r"印度|🇮🇳|\bIN\b|India|Mumbai|Delhi|Bangalore"),
    ("土耳其", r"土耳其|🇹🇷|\bTR\b|Turkey|Istanbul"),
    ("巴西", r"巴西|🇧🇷|\bBR\b|Brazil|Sao.?Paulo"),
    ("越南", r"越南|🇻🇳|\bVN\b|Vietnam|Hanoi|Ho.?Chi.?Minh"),
    ("泰国", r"泰国|🇹🇭|\bTH\b|Thailand|Bangkok"),
    ("马来西亚", r"马来西亚|🇲🇾|\bMY\b|Malaysia|Kuala.?Lumpur"),
    ("菲律宾", r"菲律宾|🇵🇭|\bPH\b|Philippines|Manila"),
    ("爱尔兰", r"爱尔兰|🇮🇪|\bIE\b|Ireland|Dublin"),
    ("瑞典", r"瑞典|🇸🇪|\bSE\b|Sweden|Stockholm"),
    ("波兰", r"波兰|🇵🇱|\bPL\b|Poland|Warsaw"),
    ("乌克兰", r"乌克兰|🇺🇦|\bUA\b|Ukraine|Kyiv"),
    ("西班牙", r"西班牙|🇪🇸|\bES\b|Spain|Madrid"),
    ("意大利", r"意大利|🇮🇹|\bIT\b|Italy|Milan|Rome"),
    ("瑞士", r"瑞士|🇨🇭|\bCH\b|Switzerland|Zurich|Geneva"),
    ("卢森堡", r"卢森堡|🇱🇺|\bLU\b|Luxembourg"),
    ("罗马尼亚", r"罗马尼亚|🇷🇴|\bRO\b|Romania|Bucharest"),
    ("匈牙利", r"匈牙利|🇭🇺|\bHU\b|Hungary|Budapest"),
    ("捷克", r"捷克|🇨🇿|\bCZ\b|Czech|Prague"),
    ("奥地利", r"奥地利|🇦🇹|\bAT\b|Austria|Vienna"),
    ("丹麦", r"丹麦|🇩🇰|\bDK\b|Denmark|Copenhagen"),
    ("挪威", r"挪威|🇳🇴|\bNO\b|Norway|Oslo"),
    ("芬兰", r"芬兰|🇫🇮|\bFI\b|Finland|Helsinki"),
    ("保加利亚", r"保加利亚|🇧🇬|\fBG\b|Bulgaria|Sofia"),
    ("塞尔维亚", r"塞尔维亚|🇷🇸|\fRS\b|Serbia|Belgrade"),
    ("希腊", r"希腊|🇬🇷|\fGR\b|Greece|Athens"),
    ("葡萄牙", r"葡萄牙|🇵🇹|\fPT\b|Portugal|Lisbon"),
    ("阿根廷", r"阿根廷|🇦🇷|\fAR\b|Argentina|Buenos.?Aires"),
    ("智利", r"智利|🇨🇱|\fCL\b|Chile|Santiago"),
    ("墨西哥", r"墨西哥|🇲🇽|\fMX\b|Mexico"),
    ("南非", r"南非|🇿🇦|\fZA\b|South.?Africa|Johannesburg"),
    ("新西兰", r"新西兰|🇳🇿|\fNZ\b|New.?Zealand|Auckland"),
    ("印尼", r"印尼|印度尼西亚|🇮🇩|\bID\b|Indonesia|Jakarta"),
    ("巴基斯坦", r"巴基斯坦|🇵🇰|\bPK\b|Pakistan"),
    ("沙特", r"沙特|🇸🇦|\bSA\b|Saudi|Riyadh"),
    ("阿联酋", r"阿联酋|🇦🇪|\bAE\b|Emirates|Dubai"),
    ("以色列", r"以色列|🇮🇱|\bIL\b|Israel|Tel.?Aviv"),
    ("新加坡2", r"", ),
]
REGION_RULES = [r for r in REGION_RULES if r[1]]
DEFAULT_REGION = "其他"
TLD_REGION = {
    "us": "美国", "jp": "日本", "hk": "香港", "tw": "台湾", "sg": "新加坡", "kr": "韩国",
    "uk": "英国", "gb": "英国", "de": "德国", "fr": "法国", "ca": "加拿大", "nl": "荷兰",
    "ru": "俄罗斯", "au": "澳大利亚", "in": "印度", "tr": "土耳其", "br": "巴西",
    "vn": "越南", "th": "泰国", "my": "马来西亚", "ph": "菲律宾", "id": "印尼",
    "ie": "爱尔兰", "se": "瑞典", "pl": "波兰", "ua": "乌克兰", "es": "西班牙",
    "it": "意大利", "ch": "瑞士", "lu": "卢森堡", "ro": "罗马尼亚", "hu": "匈牙利",
    "cz": "捷克", "at": "奥地利", "dk": "丹麦", "no": "挪威", "fi": "芬兰",
    "bg": "保加利亚", "rs": "塞尔维亚", "gr": "希腊", "pt": "葡萄牙", "ar": "阿根廷",
    "cl": "智利", "mx": "墨西哥", "za": "南非", "nz": "新西兰", "il": "以色列",
    "sa": "沙特", "ae": "阿联酋", "co": "哥伦比亚", "kz": "哈萨克斯坦",
}


def classify_region(name, server, hint=""):
    text = f"{name} {server}"
    for region, pattern in REGION_RULES:
        if region == "新加坡2":
            continue
        if re.search(pattern, text, re.IGNORECASE):
            return region
    domain = str(hint or "")
    if domain and not re.fullmatch(r"[0-9.:\[\]a-fA-F]+", domain):
        tld = domain.rsplit(".", 1)[-1].lower()
        if tld in TLD_REGION:
            return TLD_REGION[tld]
    return DEFAULT_REGION


def b64_decode(text):
    s = "".join(text.split())
    if len(s) < 16 or not re.fullmatch(r"[A-Za-z0-9+/=]+", s):
        return None
    try:
        raw = base64.b64decode(s + "=" * (-len(s) % 4), validate=True)
    except Exception:
        return None
    try:
        return raw.decode("utf-8")
    except Exception:
        return None


def http_get(url, timeout=25, retries=3):
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": UA, "Accept": "*/*"},
                             allow_redirects=True)
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() in ("iso-8859-1", "latin-1"):
                r.encoding = "utf-8"
            return r.text
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


# ---------------------------------------------------------------- 解析节点链接

def _split_hostport(text, default_port):
    host, _, port = text.rpartition(":")
    if not host:
        return text, default_port
    host = host.strip("[]")
    try:
        return host, int(port)
    except ValueError:
        return text, default_port


def _qs(query):
    return {k.lower(): v for k, v in parse_qs(query, keep_blank_values=True).items()}


def _first(q, key, default=""):
    v = q.get(key)
    return v[0] if v else default


def _apply_transport(p, q):
    network = (_first(q, "type") or _first(q, "network") or "").lower()
    if network:
        p["network"] = network
    sni = _first(q, "sni") or _first(q, "peer")
    if sni:
        p["servername"] = sni
    alpn = _first(q, "alpn")
    if alpn:
        p["alpn"] = [a for a in alpn.split(",") if a]
    security = _first(q, "security").lower()
    if security == "tls" or _first(q, "tls") == "1":
        p["tls"] = True
    elif security == "reality":
        p["tls"] = True
        p["reality-opts"] = {"public-key": _first(q, "pbk"), "short-id": _first(q, "sid")}
        fp = _first(q, "fp")
        if fp:
            p["client-fingerprint"] = fp
    elif security == "grpc" or network == "grpc":
        pass
    flow = _first(q, "flow")
    if flow and flow != "none":
        p["flow"] = flow
    host_hdr = _first(q, "host")
    path = _first(q, "path")
    if network == "ws":
        opts = {}
        if path:
            opts["path"] = unquote(path)
        if host_hdr:
            opts["headers"] = {"Host": host_hdr}
        if opts:
            p["ws-opts"] = opts
    elif network == "grpc":
        svc = _first(q, "servicename") or _first(q, "serviceName")
        opts = {}
        if svc:
            opts["grpc-service-name"] = unquote(svc)
        if host_hdr:
            opts["headers"] = {"Host": host_hdr}
        if p.get("alpn") is None and (security in ("tls", "reality") or p.get("tls")):
            opts_alpn = ["h2"]
            p["alpn"] = opts_alpn
        if opts:
            p["grpc-opts"] = opts
    elif network in ("http", "h2"):
        opts = {}
        if path:
            opts["path"] = unquote(path)
        if host_hdr:
            opts["host"] = host_hdr
        if opts:
            p["http-opts"] = opts
    elif network == "h2":
        opts = {}
        if path:
            opts["path"] = unquote(path)
        if host_hdr:
            opts["host"] = host_hdr
        if opts:
            p["h2-opts"] = opts
    elif network == "xhttp":
        opts = {}
        if path:
            opts["path"] = unquote(path)
        if host_hdr:
            opts["host"] = host_hdr
        mode = _first(q, "mode")
        if mode:
            opts["mode"] = mode
        if opts:
            p["xhttp-opts"] = opts
    if security == "reality":
        p["reality-opts"] = {"public-key": _first(q, "pbk"), "short-id": _first(q, "sid")}
    return p


def parse_link(link):
    link = link.strip().rstrip(",;")
    scheme, _, rest = link.partition("://")
    scheme = scheme.lower()
    if scheme == "ss":
        return parse_ss(rest)
    if scheme == "vmess":
        return parse_vmess(rest)
    if scheme not in ("vless", "trojan", "hysteria", "hysteria2", "hy2", "tuic", "anytls"):
        return None
    if scheme == "hy2":
        scheme = "hysteria2"
    head, _, tag = rest.partition("#")
    query = ""
    if "?" in head:
        head, _, query = head.partition("?")
    userinfo, _, hostport = head.rpartition("@")
    server, port = _split_hostport(hostport, 443)
    if not server or not port:
        return None
    q = _qs(query)
    name = unquote(tag) or (unquote(q.get("peer", [""])[0]) if q.get("peer") else "") or f"{scheme}-{server}"
    p = {"name": name, "type": scheme, "server": server, "port": int(port), "udp": True}
    if scheme in ("vless",):
        p["uuid"] = userinfo
    elif scheme in ("trojan", "hysteria", "hysteria2", "anytls"):
        p["password"] = userinfo
    elif scheme == "tuic":
        uuid_part, _, pw_part = userinfo.partition(":")
        p["uuid"] = uuid_part
        p["password"] = pw_part
    if scheme == "hysteria2":
        obfs = _first(q, "obfs")
        if obfs:
            p["obfs"] = obfs
            p["obfs-password"] = _first(q, "obfs-password")
        p["sni"] = _first(q, "sni") or _first(q, "peer") or server
        if _first(q, "insecure") == "1":
            p["skip-cert-verify"] = True
        p["tls"] = True
    elif scheme == "tuic":
        p["sni"] = _first(q, "sni") or _first(q, "peer") or server
        p["alpn"] = [a for a in _first(q, "alpn", "h3").split(",") if a]
        if _first(q, "disable_sni") == "1":
            p["disable-sni"] = True
        if _first(q, "allow_insecure") == "1":
            p["skip-cert-verify"] = True
        p["reduce-rtt"] = _first(q, "reduce_rtt", "1") == "1"
    else:
        _apply_transport(p, q)
    return p


def parse_ss(rest):
    head, _, tag = rest.partition("#")
    hostport = None
    creds = None
    if "@" in head:
        left, _, hostport = head.rpartition("@")
        decoded = b64_decode(left)
        if decoded and ":" in decoded:
            creds = decoded
        elif ":" in left:
            creds = left
        else:
            return None
    else:
        decoded = b64_decode(head)
        if not decoded or "@" not in decoded:
            return None
        creds, _, hostport = decoded.rpartition("@")
    server, port = _split_hostport(hostport, 8388)
    method, _, password = creds.partition(":")
    if not server or not method:
        return None
    name = unquote(tag) or f"ss-{server}"
    return {"name": name, "type": "ss", "server": server, "port": int(port),
            "cipher": method, "password": password, "udp": True}


def parse_vmess(rest):
    b64part, _, tag = rest.partition("#")
    decoded = b64_decode(b64part)
    if not decoded:
        return None
    try:
        j = json.loads(decoded)
    except Exception:
        return None
    host = j.get("add") or j.get("address") or j.get("v") or ""
    if not host or not j.get("port"):
        return None
    net = (j.get("net") or "tcp").lower()
    p = {
        "name": unquote(tag) or j.get("ps") or f"vmess-{host}",
        "type": "vmess",
        "server": host,
        "port": int(j["port"]),
        "uuid": j.get("id") or j.get("uuid") or "",
        "alterId": int(j.get("aid") or 0),
        "cipher": j.get("scy") or "auto",
        "udp": True,
    }
    if not p["uuid"]:
        return None
    if (j.get("tls") or "") == "tls":
        p["tls"] = True
        p["servername"] = j.get("sni") or host
    if net == "ws":
        opts = {}
        if j.get("path"):
            opts["path"] = j["path"]
        if j.get("host"):
            opts["headers"] = {"Host": j["host"]}
        if opts:
            p["ws-opts"] = opts
    elif net == "grpc":
        opts = {}
        if j.get("path"):
            opts["grpc-service-name"] = j["path"]
        if j.get("host"):
            opts["headers"] = {"Host": j["host"]}
        if opts:
            p["grpc-opts"] = opts
    elif net in ("http", "h2"):
        opts = {}
        if j.get("path"):
            opts["path"] = j["path"]
        if j.get("host"):
            opts["host"] = j["host"]
        if opts:
            p["http-opts"] = opts
    if net:
        p["network"] = net
    return p


class _Dumper(yaml.SafeDumper):
    """数字样字符串（如 0007682）必须加引号：PyYAML 视作字符串，而内核的 Go YAML
    会按八进制/浮点解析成 7.682E+03，导致节点名对不上。"""


def _quote_numeric(dumper, data):
    style = "'" if re.fullmatch(r"[0-9][0-9_.eE+\-x]*", str(data)) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _quote_numeric)


def dump_yaml(obj):
    return yaml.dump(obj, Dumper=_Dumper, allow_unicode=True, sort_keys=False,
                     default_flow_style=False)


def dedupe_key(p):
    cred = p.get("password") or p.get("uuid") or ""
    if p["type"] == "ss":
        cred = f"{p.get('cipher')}:{cred}"
    extra = ""
    for k in ("ws-opts", "reality-opts", "grpc-opts", "obfs", "network", "tls", "servername"):
        if p.get(k):
            extra += f"{k}={json.dumps(p[k], sort_keys=True, ensure_ascii=False)};"
    return f"{p['type']}|{p['server']}|{p['port']}|{cred}|{extra}"


# ---------------------------------------------------------------- 抓取来源

def expand_date(url):
    """把 {date} / {date:1} 展开成今天 / 昨天(天前)的 YYYYMMDD，适配每日归档的仓库。"""
    def rep(m):
        back = int(m.group(1) or 0)
        return time.strftime("%Y%m%d", time.gmtime(time.time() - back * 86400))
    return re.sub(r"\{date(?::(\d))?\}", rep, url)


def fetch_source(url):
    """返回 (节点dict列表, 备注)"""
    url = expand_date(url)
    try:
        text = http_get(url)
    except Exception as e:
        return [], f"抓取失败 {type(e).__name__}"
    out = []
    notes = []
    stripped = text.strip()
    decoded = None
    if not LINK_RE.search(stripped) and "proxies:" not in stripped[:4000]:
        decoded = b64_decode(stripped)
        if decoded:
            stripped = decoded
    if "proxies:" in stripped[:8000] or "proxy-groups:" in stripped[:8000]:
        try:
            data = yaml.safe_load(stripped)
            for item in (data or {}).get("proxies") or []:
                if isinstance(item, dict):
                    out.append(item)
        except Exception as e:
            notes.append(f"yaml解析失败 {e.__class__.__name__}")
    for m in LINK_RE.findall(stripped):
        p = parse_link(m)
        if p:
            out.append(p)
    if not out:
        notes.append("未解析到节点")
    return out, "; ".join(notes)


def clean_proxy(p):
    t = str(p.get("type") or "").lower()
    if t not in SUPPORTED_TYPES or t in ("direct",):
        return None
    server = p.get("server")
    if not isinstance(server, str) or not re.fullmatch(r"[A-Za-z0-9._:\-\[\]]+", server):
        return None
    try:
        port = int(p.get("port"))
    except (TypeError, ValueError):
        return None
    if not (1 <= port <= 65535):
        return None
    if t in ("vless", "tuic") and not p.get("uuid"):
        return None
    if t in ("vmess",) and not p.get("uuid"):
        return None
    if t in ("trojan", "hysteria", "hysteria2", "tuic", "anytls") and not p.get("password"):
        return None
    if t == "ss" and (not p.get("cipher") or p.get("cipher", "").lower() in ("none", "plain", "")):
        return None
    q = {"name": str(p.get("name") or f"{t}-{server}").strip(), "type": t, "server": server, "port": port}
    for k in ("uuid", "password", "cipher", "alterId", "udp", "tls", "servername", "sni", "alpn",
              "network", "ws-opts", "grpc-opts", "http-opts", "h2-opts", "xhttp-opts", "reality-opts",
              "client-fingerprint", "flow", "obfs", "obfs-password", "skip-cert-verify", "fingerprint",
              "insecure", "reduce-rtt", "disable-sni", "ip-version-6", "public-key"):
        if p.get(k) is not None:
            q[k] = p[k]
    q.setdefault("udp", True)
    ro = q.get("reality-opts")
    if isinstance(ro, dict):
        sid = str(ro.get("short-id") or "")
        if sid and (not re.fullmatch(r"[0-9a-fA-F]*", sid) or len(sid) % 2):
            return None
        if not str(ro.get("public-key") or ""):
            return None
    uuid = q.get("uuid")
    if uuid and not re.fullmatch(r"[0-9a-fA-F\-]{16,40}|auto", str(uuid)):
        return None
    return q


# ---------------------------------------------------------------- mihomo 测活

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Mihomo:
    MAX_REPAIR = 600

    def __init__(self, binary, workdir, proxies, mixed_port=None):
        self.binary = binary
        self.port = free_port()
        self.mixed = mixed_port or free_port()
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.active = list(proxies)
        self.proc = None

    def _write_config(self):
        names = [p["name"] for p in self.active]
        cfg = {
            "mixed-port": self.mixed,
            "allow-lan": False,
            "log-level": "warning",
            "external-controller": f"127.0.0.1:{self.port}",
            "secret": "",
            "unified-delay": True,
            "tcp-concurrent": True,
            "profile": {"store-selected": True, "store-fake-ip": False},
            "proxies": self.active,
            "proxy-groups": [{"name": "探测组", "type": "select", "lazy": False, "proxies": names}],
            "dns": {"enable": True, "enhanced-mode": "redir-host",
                    "nameserver": ["223.5.5.5", "https://dns.google/dns-query"]},
        }
        path = self.workdir / "probe.yaml"
        path.write_text(dump_yaml(cfg), encoding="utf-8")
        return path

    def _test_config(self, path, log):
        with open(log, "w", encoding="utf-8", errors="replace") as fh:
            r = subprocess.run([self.binary, "-t", "-d", str(self.workdir), "-f", str(path)],
                               stdout=fh, stderr=fh, timeout=120)
        return r.returncode == 0, fh.name

    def repair(self):
        """逐个剔除让内核配置校验失败的脏节点。"""
        dropped = 0
        reasons = {}
        for _ in range(self.MAX_REPAIR):
            path = self._write_config()
            log = self.workdir / "repair.log"
            try:
                ok, _ = self._test_config(path, log)
            except Exception:
                return False
            if ok:
                if reasons:
                    top = sorted(reasons.items(), key=lambda x: -x[1])[:6]
                    print(f"  剔除 {dropped} 个非法节点，原因: " + "; ".join(f"{k}×{v}" for k, v in top))
                return True
            text = log.read_text(encoding="utf-8", errors="replace")
            bad = re.findall(r"proxy (\d+): ([^\"]+)", text)
            if not bad:
                print(f"  配置校验失败且无法定位节点: {text.strip().splitlines()[-1][:160] if text.strip() else '无输出'}")
                return False
            for _idx, msg in bad:
                reasons[msg[:70]] = reasons.get(msg[:70], 0) + 1
            for idx in sorted({int(i) for i, _ in bad}, reverse=True):
                if 0 <= idx < len(self.active):
                    del self.active[idx]
                    dropped += 1
        print(f"  剔除 {dropped} 个非法节点后仍未通过校验")
        return False

    def start(self):
        if not self.repair():
            raise RuntimeError("mihomo 配置无法通过校验")
        path = self._write_config()
        errlog = open(self.workdir / "run.log", "w", encoding="utf-8", errors="replace")
        flags = ["-d", str(self.workdir), "-ext-ctl", f"127.0.0.1:{self.port}", "-f", str(path)]
        try:
            self.proc = subprocess.Popen([self.binary] + flags, stdout=subprocess.DEVNULL,
                                         stderr=errlog, stdin=subprocess.DEVNULL)
        except FileNotFoundError:
            raise SystemExit(f"找不到 mihomo 内核: {self.binary}")
        for _ in range(60):
            if self.proc.poll() is not None:
                raise RuntimeError("mihomo 启动失败，详见 output/.runtime/run.log")
            try:
                if requests.get(self.api("/version"), timeout=2).ok:
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("mihomo 控制接口超时")


    def api(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except Exception:
                self.proc.kill()

    def group_members(self):
        try:
            d = requests.get(self.api("/proxies"), timeout=10).json()
            return list(d.get("proxies", {}).get("探测组", {}).get("all", []))
        except Exception:
            return []

    def delay(self, name, timeout_ms):
        try:
            r = requests.get(self.api(f"/proxies/{quote(name)}/delay"),
                             params={"timeout": timeout_ms, "url": PROBE_URL}, timeout=timeout_ms / 1000 + 8)
            if r.ok and isinstance(r.json().get("delay"), int):
                return r.json()["delay"]
        except Exception:
            pass
        return None

    def select(self, name):
        try:
            requests.put(self.api("/proxies/%E6%8E%A2%E6%B5%8B%E7%BB%84"), json={"name": name}, timeout=5)
            return True
        except Exception:
            return False

    def measure_speed(self, name, deadline=15):
        if not self.select(name):
            return None
        proxy = {"http": f"http://127.0.0.1:{self.mixed}", "https": f"http://127.0.0.1:{self.mixed}"}
        start = time.time()
        got = 0
        try:
            with requests.get(SPEED_URL, proxies=proxy, stream=True, timeout=(10, deadline)) as r:
                for chunk in r.iter_content(65536):
                    got += len(chunk)
                    if time.time() - start > deadline:
                        break
        except Exception:
            if got == 0:
                return None
        dur = max(time.time() - start, 0.5)
        return got / dur


def test_all(kernel, proxies, rounds, threshold, timeout_ms, concurrency):
    alive = {p["name"]: [] for p in proxies}
    pool = [p["name"] for p in proxies]
    for rnd in range(rounds):
        if not pool:
            break
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            results = list(ex.map(lambda n: (n, kernel.delay(n, timeout_ms)), pool))
        passed = []
        for name, d in results:
            if d is not None and d <= threshold:
                alive[name].append(d)
                passed.append(name)
            else:
                alive[name].append(None)
        print(f"  第{rnd + 1}轮: {len(passed)}/{len(pool)} 通过 (阈值 {threshold}ms)")
        pool = passed
        time.sleep(1)
    survivors = []
    for p in proxies:
        ds = [d for d in alive[p["name"]] if d is not None]
        if len(ds) >= max(1, rounds - 1):
            q = dict(p)
            q["_delay"] = sorted(ds)[len(ds) // 2]
            q["_rounds"] = f"{len(ds)}/{rounds}"
            survivors.append(q)
    survivors.sort(key=lambda x: x["_delay"])
    return survivors


# ---------------------------------------------------------------- 生成订阅

def assign_unique_names(proxies):
    seen = {}
    for p in proxies:
        base = re.sub(r"\s+", " ", str(p.get("name") or "node")).strip()[:80] or "node"
        if base not in seen:
            seen[base] = 1
            p["name"] = base
        else:
            seen[base] += 1
            p["name"] = f"{base} #{seen[base]}"
    return proxies


def region_hint(p):
    hint = p.get("servername") or p.get("sni") or ""
    if not hint:
        for key in ("ws-opts", "grpc-opts", "http-opts"):
            opts = p.get(key) or {}
            hint = (opts.get("headers") or {}).get("Host") or opts.get("host") or ""
            if hint:
                break
    if not hint:
        try:
            hint = p.get("server") or ""
        except Exception:
            hint = ""
    return str(hint).lstrip(".")


def build_subscription(survivors, title="免费优选节点"):
    for p in survivors:
        region = classify_region(p["name"], p["server"], region_hint(p))
        p["_region"] = region
        delay = p.get("_delay")
        speed = p.get("_speed")
        label = f"{region} {p['type'].upper()} {p['server']}"
        if speed:
            label += f" {speed / 1024 / 1024:.1f}MB/s"
        elif delay:
            label += f" {delay}ms"
        p["name"] = label
    assign_unique_names(survivors)
    by_region = {}
    for p in survivors:
        by_region.setdefault(p["_region"], []).append(p["name"])
    proxies = [{k: v for k, v in p.items() if not k.startswith("_")} for p in survivors]
    names = [p["name"] for p in survivors]
    groups = [
        {"name": "🚀 自动选择", "type": "url-test", "url": PROBE_URL, "interval": 300,
         "tolerance": 30, "lazy": False, "max-failed-times": 3, "proxies": names},
    ]
    for region in sorted(by_region, key=lambda r: (-len(by_region[r]), r)):
        groups.append({"name": f"📍 {region}", "type": "select",
                       "proxies": ["🚀 自动选择"] + by_region[region]})
    groups.append({"name": "🎯 全节点", "type": "select", "proxies": ["🚀 自动选择"] + names})
    groups.append({"name": "🐟 漏网之鱼", "type": "select", "proxies": ["🚀 自动选择", "DIRECT"]})
    cfg = {
        "proxies": proxies,
        "proxy-groups": groups,
        # 必须自带 dns：客户端若设置成"遵循配置里的 DNS"，没有这一段就会退化成本地
        # 系统 DNS，境内解析不到境外域名，节点再多也连不上。
        "dns": {
            "enable": True,
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "fake-ip-filter": ["*.lan", "+.local", "dns.alidns.com", "*.googlevideo.com"],
            "default-nameserver": ["223.5.5.5", "119.29.29.29"],
            "nameserver": ["https://doh.pub/dns-query", "https://dns.alidns.com/dns-query"],
            "fallback": ["https://dns.google/dns-query", "tls://8.8.8.8:853"],
            "fallback-filter": {"geoip": True, "geoip-code": "CN"},
            "geodata-mode": False,
            "unified-delay": True,
        },
        "rules": [
            "GEOIP,CN,DIRECT",
            "MATCH,🐟 漏网之鱼",
        ],
    }
    header = (f"# {title}\n"
              f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n"
              f"# 存活节点: {len(survivors)} / 存活率见日志\n")
    return header + dump_yaml(cfg)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent
    ap.add_argument("--sources", default=str(here / "sources.txt"))
    ap.add_argument("--out", default=str(here / "output"))
    ap.add_argument("--kernel", default=os.environ.get("MIHOMO_BIN", ""))
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--threshold", type=int, default=800, help="延迟阈值 ms")
    ap.add_argument("--timeout", type=int, default=4000, help="单次探测超时 ms")
    ap.add_argument("--concurrency", type=int, default=48)
    ap.add_argument("--max-nodes", type=int, default=1200)
    ap.add_argument("--speed", type=int, default=0, help="对前 N 个存活节点实测下载速度")
    ap.add_argument("--min-keep", type=int, default=1, help="至少保留多少节点才覆盖旧订阅")
    ap.add_argument("--refresh", action="store_true", help="忽略缓存重新抓取")
    ap.add_argument("--cache-ttl", type=int, default=60, help="本地节点缓存有效期（分钟），仅本机复用")
    args = ap.parse_args()

    urls = [l.strip() for l in Path(args.sources).read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]
    cache = Path(args.out) / "pool.json"
    fresh = cache.exists() and (time.time() - cache.stat().st_mtime) < args.cache_ttl * 60
    if fresh and not args.refresh:
        pool = {dedupe_key(p): p for p in json.loads(cache.read_text(encoding="utf-8"))}
        print(f"[1/5] 复用 {args.cache_ttl} 分钟内的节点缓存: {len(pool)} 个（--refresh 可强制重抓）")
    else:
        print(f"[1/5] 抓取 {len(urls)} 个来源")
        pool = {}
        for u in urls:
            got, note = fetch_source(u)
            ok = 0
            for raw in got:
                p = clean_proxy(raw)
                if not p:
                    continue
                k = dedupe_key(p)
                if k not in pool:
                    pool[k] = p
                    ok += 1
            print(f"  {expand_date(u)}  -> 解析 {len(got)}, 新增 {ok}  {'(' + note + ')' if note else ''}")
        Path(args.out).mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(list(pool.values()), ensure_ascii=False), encoding="utf-8")
    proxies = assign_unique_names(list(pool.values()))
    print(f"[2/5] 去重后节点总数: {len(proxies)}")
    if len(proxies) > args.max_nodes:
        random.seed(42)
        proxies = random.sample(proxies, args.max_nodes)
        print(f"  超过上限，随机抽取 {args.max_nodes} 个")

    kernel_path = args.kernel or _autodetect_kernel()
    print(f"[3/5] 启动内核测活: {kernel_path}")
    workdir = Path(args.out) / ".runtime"
    mihomo = Mihomo(kernel_path, workdir, proxies)
    mihomo.start()
    try:
        loaded = len(mihomo.active)
        if loaded < len(proxies):
            print(f"  内核拒绝加载 {len(proxies) - loaded} 个格式非法节点（脏数据），已剔除")
        members = set(mihomo.group_members())
        if members:
            proxies = [p for p in proxies if p["name"] in members]
        survivors = test_all(mihomo, proxies, args.rounds, args.threshold, args.timeout, args.concurrency)
        rate = (len(survivors) / len(proxies) * 100) if proxies else 0
        print(f"[4/5] 存活 {len(survivors)}/{len(proxies)} ({rate:.1f}%)")
        if args.speed and survivors:
            print(f"  实测下载速度: 前 {min(args.speed, len(survivors))} 个")
            for p in survivors[: args.speed]:
                sp = mihomo.measure_speed(p["name"])
                p["_speed"] = sp
                if sp:
                    print(f"    {p['name'][:38]:40s} {sp / 1024 / 1024:5.2f} MB/s  {p['_delay']}ms")
    finally:
        mihomo.stop()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    if len(survivors) < args.min_keep:
        print(f"[5/5] 存活节点过少({len(survivors)})，不覆盖已有订阅")
        return 2
    (outdir / "clash.yaml").write_text(build_subscription(survivors), encoding="utf-8")
    stats = {
        "total": len(proxies),
        "alive": len(survivors),
        "alive_rate": f"{(len(survivors) / len(proxies) * 100):.1f}%" if proxies else "0%",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "by_region": {r: c for r, c in sorted(
            ((r, sum(1 for p in survivors if p.get("_region") == r))
             for r in {p.get("_region", DEFAULT_REGION) for p in survivors}),
            key=lambda x: -x[1])},
        "fastest": [{"name": p["name"], "delay": p["_delay"]} for p in survivors[:3]],
    }
    (outdir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[5/5] 已写入 {outdir / 'clash.yaml'}  ({len(survivors)} 个节点)")
    return 0


def _autodetect_kernel():
    cands = [
        r"C:\Program Files\Clash Verge\verge-mihomo.exe",
        r"C:\Program Files\Clash Verge\verge-mihomo-alpha.exe",
        str(Path.home() / "AppData/Local/io.github.clash-verge-rev.clash-verge-rev/verge-mihomo.exe"),
        "./mihomo", "mihomo",
    ]
    for c in cands:
        p = Path(c).expanduser()
        if p.suffix or "/" in c or "\\" in c:
            if p.exists():
                return str(p)
        else:
            from shutil import which
            w = which(c)
            if w:
                return w
    raise SystemExit("未找到 mihomo 内核，请用 --kernel 或环境变量 MIHOMO_BIN 指定")


if __name__ == "__main__":
    sys.exit(main())
