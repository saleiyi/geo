# Conversion V2 与基线复测验收 · 2026-09-26

本轮保留 FastAPI + 静态 HTML/CSS/JavaScript、原品牌与暖白绿配色，未升级项目依赖。定位按用户确认继续面向建站和 SEO 服务商，提供葡语、英语、简体中文。

## 已交付

- 首页明确说明 SEO + GEO 页面分析，首屏保留单个强主按钮、URL 输入、免费范围及无需登录提示。
- 能力卡按实际引擎能力描述；补充 SEO 与 GEO 的关系、三步流程、行动示例、9 项 FAQ 和底部入口。
- 报告先展示最多三项真实问题及处理建议，不生成虚构工时、排名收益或语义改写。示例始终标记虚构，内容仅演示引擎支持的结构检查。
- 三语言独立标题、description、Open Graph、Twitter、lang、canonical、hreflang 和 WebSite/WebApplication 结构化数据；方法与隐私页同步。
- 保存或导入一份浏览器本地基线，主动复测，显示检查状态变化、前后证据及可比较时的分数差值。支持 JSON、比较 Markdown 和打印 PDF。
- API 路由和请求参数不变，响应新增报告与评分版本字段；规则本身未变。未新增账户、收费、全站抓取或真实 AI 引用监控。

## 比较的证据规则

只比较相同请求 URL、最终 URL、引擎、格式和评分版本，并要求复测时间更晚。检查通过稳定的 area/id 对齐，翻译不会造成假差异。

只有 warn/fail → pass 计为已解决；只有 pass → warn/fail 计为新增问题。此前缺失、info、unknown 或此次缺失/无法确认的结果不会被当作修复或新增退化。权重或计分覆盖变化时不显示分数差值。状态改善仍未通过的检查继续列在待处理项；“变严重”是仍存在问题的子集。

基线只在用户明确保存/导入后写入 localStorage，最大 1 MiB，去掉原始页面正文；无自动上传或后台复测。新导入、保存和清除优先于此前尚未完成的文件读取。界面及导出明确说明基线未经服务器认证，状态变化不证明因果、排名、流量或实际 AI 引用。

## 验证结果

- Python：145 passed；JavaScript：26 passed。网络防护、API 配额与原有检查回归通过。仍有原有 Starlette/httpx 测试客户端弃用提示。
- 三语言 375×812 和 375×667 首屏均显示标题、输入框与主按钮；无横向溢出。667 高度下按钮底沿分别约 492、452、441 px。
- Playwright + 本机 Edge：显式保存、刷新及跨语言恢复且不自动扫描、主动复测、JSON/Markdown/PDF、导入覆盖顺序、无效/超大文件拒绝、旧版本兼容提示、禁止演示作为基线全部通过，无页面 JS 异常。
- 比较测试使用真实解析器及规则分析器处理两份**合成 HTML 夹具**，修改 description 与 viewport 后确认两项通过。HTTP API 在浏览器中被本地夹具替代，没有外部请求。这是功能测试，不是客户案例或实际收益证明。
- 测试脚本：`tests/browser/conversion_v2_smoke.py`；生成的夹具、导出文件和结构化浏览器记录位于忽略目录 `reports/conversion-v2/`。

## 截图

| 范围 | 修改前 | 修改后 |
| --- | --- | --- |
| 中文手机首屏 | [首屏](screenshots/conversion-v2-before-hero.png) | [首屏](screenshots/conversion-v2-after-hero.png) |
| 中文手机整页 | [整页](screenshots/conversion-v2-before-mobile.png) | [整页](screenshots/conversion-v2-after-mobile.png) |

[桌面整页](screenshots/conversion-v2-after-desktop.png) · [测试夹具生成的比较，非客户案例](screenshots/conversion-v2-fixture-comparison.png)

修改前页面取自本轮开始时的 Git HEAD，使用同一 375×812 视口。

## 性能复核

使用 Lighthouse 13.5.0、本机 Edge、默认移动设备模拟。修改前后的静态快照均由 Python http.server 提供，顺序复测时没有并行运行浏览器验收。

| 运行 | 性能 | 可访问性 | FCP | LCP | TBT | CLS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 原版首次静态基线 | 100 | 96 | 1.1 s | 1.2 s | 90 ms | 0.01 |
| 新版本地 FastAPI 预览 | 99 | 97 | 1.4 s | 1.6 s | 0 ms | 0 |
| 新版静态页，与功能验收重叠运行 | 94 | 100 | 1.1 s | 1.6 s | 280 ms | 0.01 |
| 原版顺序复测 | 100 | 96 | 1.1 s | 1.4 s | 70 ms | 0 |
| 新版顺序复测 | 99 | 100 | 1.1 s | 1.5 s | 110 ms | 0.01 |

顺序结果未见明显性能退步，但存在本机运行波动，不作为生产性能承诺。最后一处低对比文字在 FastAPI 那次测量后修正，因此最终静态页可访问性为 100。静态页的 SEO 自动检查为 100；真实 FastAPI 预览因刻意保持 noindex 为 66，未为提高分数而解除预览禁索引。

这些 JSON 报告均成功生成，`runtimeError=null`；Lighthouse 命令在退出清理 Windows 临时目录时遇到 EPERM，退出码为 1，不能描述为命令完全无错误。原始 JSON 及汇总保存在 `reports/lighthouse-*.json` 和 `reports/conversion-v2/`。未升级项目依赖；临时 npm 缓存仅用于本地验收。

## 尚未完成的商业与部署条件

本地预览仍保持 noindex，未发布到公网。正式域名、托管账户、HTTPS、运营联系人和 Search Console 尚未配置。没有客户、收费或盈利数据；[首单验证方案](COMMERCIAL_VALIDATION.md) 是待执行方案。工具输出保持单页技术证据边界，不能作为真实 AI 引用监测结果。
