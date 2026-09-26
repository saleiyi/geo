# 外部试用发布准备 · 2026-09-26

当前没有公网部署、远程 Git 仓库或托管账户连接。新增配置与模板是可执行的准备工作，不是已上线的证据。当前本地预检会如实返回 `configuration_ready: false`。

## 先准备真实信息

在目标环境的环境变量中填写以下内容，无需将密码或密钥写入文档：

| 配置 | 含义 |
| --- | --- |
| `SITE_URL` | 实际 HTTPS origin，无路径；Render 上可省略，由平台 `RENDER_EXTERNAL_URL` 提供 |
| `OPERATOR_NAME` | 对外负责此服务的真实个人或主体名称 |
| `CONTACT_EMAIL` | 一个可接收咨询的公开邮箱；不是显示名称或地址列表 |
| `HOSTING_PROVIDER` | 实际托管商名称 |
| `PRIVACY_LOG_NOTICE_PT/EN/ZH` | 同一实际日志处理规则的葡语、英语、中文说明，包含应用与托管/代理的日志及保留期限 |

三语隐私页直接展示这些信息，按 HTML 纯文本转义。说明文字应来自实际运营决定和托管配置；填写文案不会改变服务器日志策略。信息未填时继续显示明确的预览提示，不虚构主体或邮箱。

本地开发仍可在这些字段为空时运行。`SITE_INDEXABLE=true` 必须同时具备 HTTPS origin 和上述六个运营字段，否则配置校验失败；Search Console 验证不是技术前置。发布预检检查的是**配置完整性**，不能验证主体真实性、服务稳定性或任何法律结论。

```powershell
.venv\Scripts\python.exe -m mandapi_geo.preflight --stage local
.venv\Scripts\python.exe -m mandapi_geo.preflight --stage preview
.venv\Scripts\python.exe -m mandapi_geo.preflight --stage production
```

预检只读取配置，不发网络请求、不输出密钥或配置原值。通过时退出 0，缺项或无效时退出 1。`preview` 要求保持 noindex，`production` 要求明确开启索引；两者都不能代替下面的现场验收。

## 可选路径：Render 平台域名试用

Render 提供 `onrender.com` 地址及 HTTPS，Docker web service 可承载现有 FastAPI 程序，因此第一次外部试用可以不购买独立域名。[Web Services](https://render.com/docs/web-services)、[平台环境变量](https://render.com/docs/environment-variables)

仓库根目录的 `render.yaml` 定义一个免费 Docker web service，不添加数据库、付费模型或自动部署。首次创建会要求填写真实运营名称、邮箱和三语日志说明；托管商固定为 Render。启动命令先执行 preview 预检，再以一个 worker 在 8000 端口启动。字段依据 [Blueprint 官方规范](https://render.com/docs/blueprint-spec)；模板已通过本地 YAML 解析与默认项检查，尚未提交给平台验证。

实际操作顺序：

1. 登录用户自己的 Git 提供商和 Render 账户，将已验收代码推送到用户授权的仓库。当前尚无仓库地址，不生成假的 Deploy 按钮。
2. 在 Render 连接该仓库，选择 Blueprint，核对仅创建这一个免费 web service。名称如与已有服务重名，先修改模板，避免套用到已有服务。
3. 填写真实信息，检查账户计费和限额，再创建。`sync: false` 只在首次创建提示输入；后续修改需要到服务环境配置中进行，不会随 Git 更新自动覆盖。[环境变量规则](https://render.com/docs/blueprint-spec#prompting-for-secret-values)
4. 查看部署日志中的预检结果及 `/health`，再打开平台地址的 `/`、`/en`、`/zh` 和三语隐私页。确认 canonical 使用平台 HTTPS 地址，全部仍 noindex、sitemap 无索引页面。
5. 完成真实扫描、客户端配额、失败提示与复测验收之后，才把链接发给愿意参加的服务商。

免费实例会休眠、冷启动、重启，重启会清空本应用的内存配额；高出站流量可能触发平台暂停。带宽及构建额度用尽时，是否计费或暂停取决于账户的付款方式和限额。它适合少量预约试用，不能描述为稳定商业托管。未在本轮开通服务、添加付款方式或产生托管费用。[免费实例限制](https://render.com/docs/free)

## 必须在目标环境核实

- **代理身份与配额：** 模板保留 `--no-proxy-headers`，不会信任访客可伪造的转发头。平台转发可能让所有访客共用代理地址的每日 3 次额度。先核对平台实际代理链，在两个真实客户端测试；没有证据时不得宣传为独立用户额度，也不得简单改为信任 `*`。可先由运营人员预约单人试点，完成身份隔离后再开放多人自助试用。
- **出站访问和超时：** `/health` 只证明进程响应；还要验证目标环境的 DNS、公开 HTTPS 抓取、重定向与辅助文件请求，检查入口允许扫描完成。
- **运行与数据：** 平台构建 Dockerfile 不会继承 Compose 的资源、日志轮转和代理参数；分别核对实际限制与日志保留。当前无服务器报告数据库，浏览器基线只留在参与者自己的设备。
- **回退：** 记录 Git 提交、部署版本及配置，验证可回退；模板关闭自动部署，后续发布主动触发。

本机没有可用 Docker 命令，本轮没有验证 Linux 镜像构建和容器启动。平台账户、真实部署、HTTPS 及以上现场检查均仍待完成。

## 首轮邀请与证据

已整理 [5 家候选服务商](PILOT_CANDIDATES.md) 和 [竞品现状](MARKET_EVIDENCE.md)。候选均未联系；官网相似业务不表示他们需要本工具或愿意付款。

按 [首单验证方案](COMMERCIAL_VALIDATION.md) 先了解一次真实交付，再邀请一个获准页面做修复复测。每次记录实际使用、交付工时、复用和付款；没有证据的格子保持未知。目标仍是持续盈利的 SaaS，目前没有证据证明已实现。
