# clash-node-harvest

采集公开免费节点源 → 逐个测活、不通的直接丢掉 → 生成一份统一的 Clash(Mihomo) 订阅。

## 结论先说：必须在被测的那台机器上测活

2026-09-29 实测（本机国内网络）：

| 订阅 | 谁筛的 | 节点数 | 国内 HTTPS 探测可用 |
| --- | --- | --- | --- |
| Actions 产出（`sub` 分支） | 美国 runner | 356 | **0 个**（最低延迟那批直接 RST） |
| 本机产出（`output/clash.yaml`） | 这台机器 | 26 | **18 个**（延迟 43–1149ms，前 10 快全过） |

原因是"能连通"和"回国能用"是两件事：Actions 只能证明节点在美国可达，而免费节点里大量
Cloudflare 前置的 VLESS/Trojan 对境内流量要么握手超时要么立刻 RST。所以这个仓库是**双轨**：

- **主路（推荐）**：Windows 计划任务每 6 小时跑一次 `run_local.cmd`，用本机网络测活，
  覆盖 `output/clash.yaml`。Clash Verge 里订阅选"本地文件"指向它 —— 地址仍然只有一个。
- **备用**：GitHub Actions 每 3 小时产出一份"全球可达"清单，换设备或本机没跑时用：
  `https://raw.githubusercontent.com/IYIcode/clash-node-harvest/sub/clash.yaml`

## 用法（Clash Verge）

订阅 → 新建 → 类型选"本地文件"（或"远程配置"用备用链接）→ 启用 → 打开系统代理/TUN。
切节点用 `🚀 自动选择`（每 5 分钟按同样口径自己重测），或按地区分组 `📍 香港` 之类手选。

计划任务注册（在当前目录执行，不需要管理员）：

```powershell
powershell -ExecutionPolicy Bypass -File .\clash_node_harvest\register_task.ps1
# 撤销： Unregister-ScheduledTask -TaskName clash-node-harvest-local -Confirm:$false
# 看日志： type .\clash_node_harvest\output\cron.log
```

## 测活口径

节点必须通过 **HTTPS 探测**（`https://cp.cloudflare.com/generate_204`）才算活着：实测同一批节点
明文 HTTP 能过 14/23，换成 HTTPS 只剩 6/23 —— 免费节点最常见的坏法是隧道能建、TLS 搬运不了，
只看明文探测会把这类"假活"节点留在订阅里。同一条探测也写进订阅的 `url-test` 组，客户端按同样口径复查。

抽样规模：11 个源去重约 1.4 万节点，随机抽 2500 个测活，国内通过 26 个（1.0%）。免费节点的
天花板就是这个量级，且每天失效重来 —— 所以才要每 6 小时自动重筛。

## 手动跑一次

```bash
pip install -r requirements.txt
# Windows 下可直接复用 Clash Verge 自带内核
set MIHOMO_BIN=C:/Program Files/Clash Verge/verge-mihomo.exe
# 国内直连抓 raw.githubusercontent.com 基本不通，本机跑要借 Verge 的代理（它得开着）
set HTTPS_PROXY=http://127.0.0.1:7890
python harvest.py --max-nodes 2500 --rounds 2 --threshold 2500 --timeout 6000
# 或者直接双击 run_local.cmd，日志追加到 output/cron.log
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

- 主路的测活必须在你自己的网络里做 —— 换 vantage 结论就翻车（见上表）。Actions 那份只当
  跨设备备用，别指望它在国内能用。
- 本机跑要 Verge 开着（`HTTPS_PROXY=127.0.0.1:7890` 抓源用）；抓不到源时脚本会直接退出，
  不会用空结果覆盖已有订阅（`--min-keep`）。
- 同一出口 IP 连打 raw.githubusercontent 会被限流（实测 11 个源只有 1 个成功）。所以：每个源
  之间歇 1.5 秒、403/429 退避重试，且**抓到的节点数远少于缓存时判定为限流、保留旧节点池**
  （缓存低于 500 个视为不可信，下次强制重抓）。订阅不会被一次坏运行拖垮。
- 单个格式非法的脏节点（错误的 REALITY short-id、空 key 等）会被内核校验自动剔除，不需要额外处理。
- 订阅自带 fake-ip DNS 段：客户端若选"遵循配置的 DNS"也能直接解析境外域名。
- 免费节点会记录流量，不要登录敏感账号。
