# 部署 MandAPI GEO

此仓库提供单实例部署配置，尚未配置正式域名、服务器、远程发布仓库或 TLS 证书。下面步骤不会购买服务或创建账户。当前交付环境没有可用的 Docker 命令，因此 Dockerfile / Compose 仅进行了静态检查，容器构建、启动和真实反向代理仍需在目标环境验收。

## 1. 本地确认

在仓库根目录运行：

```powershell
uv venv
uv pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest tests -q
```

本地页面通过 `.venv\Scripts\python.exe -m uvicorn mandapi_geo.api:app --host 127.0.0.1 --port 8000 --no-proxy-headers` 启动。网页文件位于 `web/`；修改生成源后运行 `.venv\Scripts\python.exe web/build_pages.py` 并检查生成文件。Playwright 可用于额外的真实浏览器检查，不属于生产依赖。

## 2. 生产依赖

`requirements.lock` 记录生产依赖的精确版本、环境条件和文件哈希。容器使用 Python 3.12，安装命令为：

```sh
python -m pip install --no-cache-dir --require-hashes -r requirements.lock
```

更新依赖时，在开发环境使用 uv 重新生成兼容 Python 3.12 / Linux 的锁文件，并审查变更、运行测试，再重新构建镜像。不要把某台 Windows 虚拟环境的 `pip freeze` 当作容器锁文件。使用跨平台锁定的示例命令为：

```sh
uv pip compile pyproject.toml --python-version 3.12 --universal --generate-hashes --output-file requirements.lock
```

镜像从 `/app` 源代码目录直接运行 `python -m uvicorn`，不需要安装本项目的 wheel。`mandapi_geo/` 与 `web/` 都被复制进镜像；只复制 Python 包会造成营销页面或静态资源 404。`python:3.12-slim` 是可更新标签，依赖哈希不等于操作系统镜像固定；正式发布记录镜像 digest，以便回退和审计。

## 3. 构建与启动

先复制 `.env.example` 为 `.env`，保留默认的 `SITE_INDEXABLE=false`。`.env` 被 Git 和 Docker 构建上下文忽略，不写进镜像。

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose build --pull
docker compose up -d
docker compose ps
docker compose logs --tail 100 geo
Invoke-RestMethod http://127.0.0.1:8000/health
```

仅首次复制 `.env`，不要覆盖已有生产配置。Linux / macOS 可使用 `cp .env.example .env` 和 `curl --fail http://127.0.0.1:8000/health`。

默认配置：

| 项目 | 行为 |
| --- | --- |
| Python / 进程 | Python 3.12 slim；单个 Uvicorn worker |
| 运行身份 | UID / GID 10001，非 root |
| 文件系统 | Compose 设置只读根文件系统，`/tmp` 为 64 MiB 临时内存目录 |
| 端口 | 容器监听 8000；宿主机仅映射 `127.0.0.1:8000` |
| 健康检查 | 每 30 秒请求容器内 `/health`；健康不代表外部抓取或 DNS 正常 |
| 资源 | 512 MiB 内存上限、128 进程上限、丢弃 capabilities |
| 日志 | 关闭 Uvicorn access log；容器 stdout/stderr 仍保留，最多 3 × 10 MiB 轮转 |
| 持久数据 | 无报表数据库或数据卷；临时限流计数重启即清空 |

生产不要使用 `--reload`，也不要增加 worker 或副本数来绕过拥塞。当前限流是进程内状态。

## 4. HTTPS 与客户端 IP

由实际托管环境提供 HTTPS 终止和反向代理；容器端口保持仅本机可达。若反代也在容器中，应使用隔离的 Docker 网络，并确保只有该代理能访问应用端口。

`compose.yaml` 启用了 Uvicorn 的 proxy-header 解析，但默认 `FORWARDED_ALLOW_IPS` 为空，**不信任任何来源的转发 IP**。正式启用前，确认应用实际连接的直接代理 peer IP，再将该固定、已知地址写入 `.env`。Docker NAT 下这个地址可能是网桥网关，并不必然是 `127.0.0.1`。不要使用 `*`，不要信任所有内网地址，也不要把客户端可伪造的 `X-Forwarded-For` 直接交给限流器。Uvicorn 的信任参数见 [官方 settings](https://www.uvicorn.org/settings/)。

在代理侧清除客户端提交的转发头，由可信代理重新写入真实客户端地址和协议。存在 CDN / 多级代理时，需要在每一跳明确可接受的来源，并验证最终 `request.client.host` 的结果。未正确配置时，所有访客可能共用代理 IP 的每日 3 次额度。

代理至少需要保留普通 POST 请求及 JSON 响应、支持 8 KiB 请求体，并允许足够的响应等待时间。默认每个网络请求有 15 秒总时限，一次扫描还会读取多个辅助资源；网页等待上限为 120 秒。可从代理 130 秒读取超时起步，在目标环境验证。若调高 `SCAN_TIMEOUT` 或启用额外 LLM 摘要，应协调服务器和网页等待时间，而非仅修改一层。边缘还应限制请求速率和并发连接；应用内扫描并发限制不替代入口层容量保护。

## 5. 开启正式索引

确定域名和 HTTPS 可用后，在 `.env` 设置真实值：

```dotenv
SITE_URL=https://你的实际域名
SITE_INDEXABLE=true
GOOGLE_SITE_VERIFICATION=你的实际验证值
```

上述域名和验证值是说明占位符，必须替换；不能直接用于部署。`SITE_URL` 必须是公开 HTTP(S) origin，不能包含用户名、密码、查询、片段或 `/geo` 等子路径。只有 HTTPS origin 配合 `SITE_INDEXABLE=true` 才允许索引。

环境变量修改后执行 `docker compose up -d --force-recreate`，因为设置在进程内缓存。开启索引后：

- 12 个页面（三种语言 × 首页、方法、隐私、指南）使用一致的正式 canonical 和 hreflang。
- `/robots.txt` 允许公开页面、禁止 `/api/`，并声明 sitemap。
- `/sitemap.xml` 提供公开页面地址及语言替代关系。
- API 仍返回 `X-Robots-Tag: noindex, nofollow` 和 `Cache-Control: no-store`。

上线前必须补齐真实运营主体、隐私联系邮箱、托管商及日志保留说明；仓库不虚构这些信息。验证 Search Console 所有权，提交正式 sitemap，然后观察真实抓取 / 索引情况。没有域名或 HTTPS 时继续保持 noindex；不要将本地预览地址提交给搜索引擎。

## 6. 限流、网络与隐私边界

`FREE_SCAN_DAILY_LIMIT=3`、`MAX_CONCURRENT_SCANS=2` 是默认值。限流按服务端认可的客户端 IP 计算，IP 以加盐 HMAC 键短暂保存在单个进程内；UTC 00:00 重置，重启清空。进入扫描的失败请求也会消耗次数；被并发门禁拒绝的请求不会消耗额度。同一 NAT 后的访客会共享额度。扩大到多个进程 / 副本前，先部署共享限流存储或可靠的边缘统一配额。

抓取仅接受公开 HTTP(S) 地址，拒绝私网、回环、链路本地等目标；DNS 所有结果必须通过检查，连接固定到已验证 IP；重定向逐跳验证。环境代理不会被扫描器采用。每次最多 5 跳重定向、HTML 解压后最多 2 MiB、辅助文件最多 512 KiB、最多尝试 3 个 sitemap。生产网络层可进一步限制出站访问，避免依赖应用校验作为唯一边界。

不持久化报表不代表完全无数据处理：请求中使用客户端 IP，运行或托管平台日志可能记录访问元数据，下载后的网页在内存解析。用户在浏览器导出的文件由其自行保存。不要把完整请求体、目标 URL 查询参数、报告正文或密钥加入访问日志。

`PUBLIC_AI_SUMMARY=false` 是默认值。开启它并配置 `LLM_API_KEY` 后，葡萄牙语 API 请求可以发送域名、评分和部分问题描述给 `LLM_BASE_URL` 对应服务商，并可能产生费用；英语 / 中文 API 摘要当前不支持。上线前确认处理目的、供应商、留存条件与费用预算，更新隐私说明。规则扫描不依赖 LLM，也不会测量真实搜索排名或 AI 引用。

## 7. 发布验收与维护

每次发布记录 Git 提交、锁文件变更、镜像 digest 和配置变更；保留可回退的上一镜像与环境配置，不将密钥放入仓库。

验收至少包括：

1. `/health`、三语言页面、CSS / JS / 图标均可访问；移动端、桌面端、键盘操作正常。
2. 每种语言可提交公开页面、展示报告、导出 JSON / Markdown；403、429、超时等失败提示可理解。
3. 私网输入被拒绝；模拟额度用完得到 429，并发拥塞得到 503；两个不同客户端不会误共用代理额度。
4. 正式 canonical、12 条 sitemap、hreflang、robots、noindex 开关与验证标签符合环境配置。
5. 容器非 root、仅预期端口可达、TLS 正常、健康检查生效、日志轮转正常；停止 / 回退流程可执行。

默认 API 免费额度为 3 次，人工验收多个页面时应有计划地使用测试环境；不要为了验收随意取消生产保护。浏览器取消请求不保证后台同步扫描立即终止，已接纳的工作可能继续到请求时限。

后续优先完成正式部署与真实用户反馈，再分别建设真实 AI 引用测量、带预算的全站爬取。账户、历史任务和计费应以验证过的使用需求与付费意愿为依据。

容器参数参考：[Dockerfile](https://docs.docker.com/reference/dockerfile/)、[Compose services](https://docs.docker.com/reference/compose-file/services/)。
