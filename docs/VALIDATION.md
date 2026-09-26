# 验收记录 · 2026-09-26

本轮是本地可部署版本验收，未发布到公网。分支：`codex/professional-geo`。

后续首页转化与基线复测验收见 [Conversion V2](CONVERSION_V2.md)：145 项 Python、26 项 JavaScript 及三语浏览器流程通过。以下保留基础版本的真实扫描和部署记录。

再后续的外部试用准备新增 27 项配置、隐私渲染和预检测试，Python 合计 **172 passed**。三语运营信息在 375×812 浏览器中无横向溢出，缺省文案本地化，无模板占位符泄露。预检当前准确返回缺少真实运营信息与 HTTPS origin；Render 模板仅完成 YAML/默认项检查及官方规范对照，没有容器或平台部署证据。详见 [外部试用准备](EXTERNAL_PILOT.md)。

## 自动化回归

执行 `.venv\Scripts\python.exe -m pytest tests -q`：**145 passed**。

覆盖网络地址/DNS与重定向安全、下载体积与截止时限、robots 路径优先级、索引指令、中文分析、评分观察项、三语报告、API配额与并发、元数据及站点地图。存在 FastAPI/Starlette 测试客户端针对 httpx 的弃用提示；当前测试通过，未来依赖升级时处理。

已将生产依赖按 `requirements.lock` 的哈希安装到本地 Python 3.12 环境并再次完成回归。锁文件采用 universal 解析。

## 浏览器验证

使用 Playwright 驱动本机 Edge，无扩展或第三方统计脚本：

- 葡语、英语、中文首页均返回 200；示例报告明确标记虚构，领域筛选和 JSON 下载成功。
- 中文在 375、390、768 像素视口下无水平溢出；桌面与手机截图已人工检查。
- 12 个页面的本地链接、样式、脚本与分享图片均返回 HTTP 200。
- 真实扫描 `https://example.com/` 成功，报告含 34 项检查，显示单页范围和启发式限制。分数是当次技术检查的产物，不作营销或跨版本基准。
- 真实报告 JSON、Markdown 下载与浏览器 PDF 输出成功；原始报告存于本地忽略目录 `reports/`。
- 内网地址拒绝；模拟 429、取消等待、恶意 HTML 文本作为纯文本显示均通过；无页面 JavaScript 异常。
- Windows 的 `.js` 错误 MIME 关联已修复，保留 `nosniff`，脚本按 `text/javascript` 提供。
- 浏览器验证结束时，刻意挂起的取消请求产生测试驱动清理阶段的 `CancelledError`，页面没有对应异常；取消状态与重新启用按钮的断言均通过。

## 截图

- `screenshots/professional-zh-hero.png`：中文版首屏。
- `screenshots/professional-zh-desktop.png`：中文版完整首页。
- `screenshots/professional-zh-mobile-390.png`：手机版首页。
- `screenshots/verified-zh-report.png`：真实 example.com 扫描报告。
- 其余 `professional-*-report.png` 为明确标注的示例报告，不是真实扫描。

## 尚未验证 / 上线依赖

- 本机没有 Docker，Dockerfile/Compose 只完成静态检查，未执行镜像构建。
- 未配置公网域名、服务器、TLS、运营联系方式或 Search Console；没有公共上线地址。
- 未测真实 AI 引用、搜索排名、生产负载、收费流程或全站爬取；这些能力尚未实现。
- 默认不开启索引、不调用付费 LLM。生产准备和下一阶段任务见 `DEPLOYMENT.md` 与根目录 README。
