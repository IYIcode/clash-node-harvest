# clash-node-harvest

采集公开免费节点源 → 测活淘汰不通的 → 生成一份统一的 Clash(Mihomo) 订阅。

GitHub Actions 每 3 小时跑一次，结果强推到 `sub` 分支，订阅地址：

```
https://raw.githubusercontent.com/<你的用户名>/clash-node-harvest/sub/clash.yaml
```

## 本地运行

```bash
pip install -r requirements.txt
# Windows 下可直接复用 Clash Verge 自带内核
MIHOMO_BIN="C:/Program Files/Clash Verge/verge-mihomo.exe" python harvest.py
# 国内直连测试建议放宽阈值，并对前 N 个存活节点实测下载速度
python harvest.py --max-nodes 1200 --rounds 2 --threshold 2000 --speed 10
```

产物在 `output/clash.yaml`（订阅）和 `output/stats.json`（存活率、地区分布）。

## 常用参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--rounds` | 3 | 测活轮数，至少通过 rounds-1 轮才保留 |
| `--threshold` | 800 | 延迟阈值 ms，超过视为不可用 |
| `--timeout` | 4000 | 单次探测超时 ms |
| `--max-nodes` | 1200 | 参与测速的节点上限（超出随机抽样） |
| `--concurrency` | 48 | 并发探测数 |
| `--speed` | 0 | 对前 N 个存活节点实测下载速度 MB/s |
| `--min-keep` | 1 | 存活节点少于该值时不覆盖旧订阅 |

## 数据源

`sources.txt` 每行一个 URL，支持三种格式自动识别：Clash YAML（`proxies:`）、
base64 订阅、以及内嵌 `ss/vmess/vless/trojan/hysteria2/tuic/anytls` 链接的网页文本。
`{date}` / `{date:1}` 会展开成今天/昨天的 `YYYYMMDD`，用于每日归档仓库。
源失效直接增删行即可。

## 注意

- Actions 在美国网络测速，筛出的是"全球可达"的节点；回国是否可用由订阅里的
  `url-test` 组在你本机每 5 分钟重新探测兜底。
- 单个格式非法的脏节点会被内核校验自动剔除，不需要额外处理。
- 免费节点会记录流量，不要登录敏感账号。
