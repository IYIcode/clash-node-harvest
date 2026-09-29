# clash-node-harvest

采集公开免费节点源 → 逐个测活、不通的直接丢掉 → 生成一份统一的 Clash(Mihomo) 订阅。

GitHub Actions 每 3 小时自动重筛一次，结果强推到 `sub` 分支，订阅地址（只有一个）：

```
https://raw.githubusercontent.com/IYIcode/clash-node-harvest/sub/clash.yaml
```

## 用法（Clash Verge）

订阅 → 新建 → 类型选"远程配置" → 粘贴上面的链接 → 启用 → 打开系统代理/TUN。
切节点用 `🚀 自动选择`（每 5 分钟自己重测），或按地区分组 `📍 香港` 之类手选。

## 测活口径

节点必须通过 **HTTPS 探测**（`https://cp.cloudflare.com/generate_204`）才算活着：实测同一批节点
明文 HTTP 能过 14/23，换成 HTTPS 只剩 6/23 —— 免费节点最常见的坏法是隧道能建、TLS 搬运不了，
只看明文探测会把这类"假活"节点留在订阅里。同一条探测也写进订阅的 `url-test` 组，客户端按同样口径复查。

实测规模与存活率（本机国内网络，2026-09-29）：11 个源去重约 1.4 万节点，抽样 2500 个测活得
26 个通过 HTTPS 探测（1.0%）；再拿这 26 个逐个真打一次外网请求，18 个当场确认能出网
（延迟 43–1149ms，前 10 快的全过），剩下的是分钟级抖动的不稳定节点。免费节点的天花板就是
这个量级，且每天失效重来。

## 本地运行

```bash
pip install -r requirements.txt
# Windows 下可直接复用 Clash Verge 自带内核
set MIHOMO_BIN=C:/Program Files/Clash Verge/verge-mihomo.exe
# 国内直连抓 raw.githubusercontent.com 基本不通，本机跑请挂代理
set HTTPS_PROXY=http://127.0.0.1:7890
python harvest.py --max-nodes 2500 --rounds 2 --threshold 2500 --timeout 6000
```

产物在 `output/clash.yaml`（订阅）和 `output/stats.json`（存活率、地区分布、最快节点）。
节点池缓存 `output/pool.json` 保留 60 分钟，重复测速不用重新抓源（`--refresh` 强制重抓）。

## 常用参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--rounds` | 3 | 测活轮数，至少通过 rounds-1 轮才保留 |
| `--threshold` | 800 | 延迟阈值 ms，超过视为不可用（HTTPS 探测含 TLS 握手，比明文高 100–500ms） |
| `--timeout` | 4000 | 单次探测超时 ms |
| `--max-nodes` | 1200 | 参与测速的节点上限（超出随机抽样） |
| `--concurrency` | 48 | 并发探测数 |
| `--speed` | 0 | 对前 N 个存活节点实测下载速度，写进节点名 |
| `--min-keep` | 1 | 存活节点少于该值时不覆盖旧订阅 |
| `--cache-ttl` | 60 | 节点池缓存有效期（分钟） |

## 数据源

`sources.txt` 每行一个 URL，支持三种格式自动识别：Clash YAML（`proxies:`）、
base64 订阅、以及内嵌 `ss/vmess/vless/trojan/hysteria2/tuic/anytls` 链接的网页文本。
`{date}` / `{date:1}` 会展开成今天/昨天的 `YYYYMMDD`，用于每日归档仓库。
源失效直接增删行即可。

## 注意

- Actions 在美国网络测速，筛出的是"全球可达 + 能搬 TLS"的节点；回国链路是否可用由订阅里的
  `url-test` 组在你本机每 5 分钟重新探测兜底，所以阈值故意放宽（2500ms）以保留候选。
- 单个格式非法的脏节点（错误的 REALITY short-id、空 key 等）会被内核校验自动剔除，不需要额外处理。
- 订阅自带 fake-ip DNS 段：客户端若选"遵循配置的 DNS"也能直接解析境外域名。
- 免费节点会记录流量，不要登录敏感账号。
