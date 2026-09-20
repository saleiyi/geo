# MandAPI GEO - GitHub 复用池（验真版 v2）

> 验真方法：**直连 GitHub API 读仓库元数据**。
> 注意：GitHub 的 `search` 是语义匹配，会漏；**不能用"搜不到"推断"不存在"**。
> 所有数据取自 2026-09-20 API 返回值。

## 0. 验真总表

| 仓库 | Stars | License | 最后推送 | 语言 | 结论 |
| --- | ---: | --- | --- | --- | --- |
| [Auriti-Labs/geo-optimizer-skill](https://github.com/Auriti-Labs/geo-optimizer-skill) | 850 | MIT | 2026-09-20 | Python | ✅ **GEO 层首选** |
| [elmohq/elmo](https://github.com/elmohq/elmo) | 343 | MIT | 2026-09-19 | TypeScript | ✅ **Monitor 层** |
| [crawlseo/crawlseo](https://github.com/crawlseo/crawlseo) | 597 | MIT | 2026-09-05 | TypeScript | ✅ **SEO 监控层** |
| [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | 83,945 | Apache-2.0 | 2026-09-18 | Python | ✅ **抓取层** |
| [puneetindersingh/open-seo-crawler](https://github.com/puneetindersingh/open-seo-crawler) | 46 | MIT | 2026-08-04 | JavaScript | ✅ 备选爬虫 |
| [MelnixDev/seo-crawl-audit](https://github.com/MelnixDev/seo-crawl-audit) | 0 | MIT | 2026-09-10 | JavaScript | ⚠️ 无社区验证 |
| [sprawf/geoscore](https://github.com/sprawf/geoscore) | 9 | **无** | 2026-05-17 | TypeScript | 🚨 **禁用代码，只读思路** |
| [langgenius/dify](https://github.com/langgenius/dify) | - | 自定义 | - | Python | ✅ 工作流 |
| [n8n-io/n8n](https://github.com/n8n-io/n8n) | - | 自定义 | - | TypeScript | ✅ 自动化 |

## 1. 领警示：GeoScore 的 license 问题

`sprawf/geoscore` 的 API 返回 `"license": null`。

**没有 license 不等于开源。** 默认版权法下，作者保留所有权利（all rights reserved）。
把它 fork 成葡语 SaaS 收费 = 侵权风险，且无法在尽调中自证。

同时它只有 9 stars、最后推送 2026-05-17（停滞 4 个月）。

**处置：** 只阅读它的 Cloudflare Workers + D1 架构作为参考，**不复制代码**。
免费获客入口改由 `geo-optimizer-skill` 承担。

## 2. 核心四件套（修订后架构）

```text
                    MandAPI GEO

                   用户网址 / 域名
                         |
                         v
              +----------------------+
              |  geo-optimizer-skill |   GEO 审计 (850★, MIT)
              |  AEO / llms.txt /    |
              |  schema / citation   |
              +----------+-----------+
                         |
        -----------------+-----------------
        |                                 |
        v                                 v
  +-------------+                 +--------------+
  |  crawlseo   |  597★ MIT       |     elmo     |  343★ MIT
  |  SEO 监控    |                 |  AI 可见度    |
  |  CWV / GSC  |                 |  品牌引用     |
  +------+------+                 +-------+------+
         |                                |
         +---------------+----------------+
                         v
                 +---------------+
                 |     Dify      |   AI 报告编排
                 +-------+-------+
                         v
                 +---------------+
                 |   MandAPI     |   多模型 / 成本控制
                 +---------------+
```

抓取层统一走 `unclecode/crawl4ai`（83,945★，Apache-2.0，可商用）。

## 3. 分层落地策略（第一版）

原则：**能跑 > 完美**。第一版只用最少外部依赖。

| 层 | 第一版怎么做 | 何时引入外部仓库 |
| --- | --- | --- |
| 抓取 | 本仓库 `mandapi_geo/fetcher.py`（httpx） | 遇到 JS 渲染站时换 Crawl4AI |
| SEO 分析 | 本仓库 `analyzers/seo.py` | 需要多页爬取时接 crawlseo |
| GEO 分析 | 本仓库 `analyzers/geo.py` | 需要引用追踪时接 geo-optimizer-skill |
| 报告 | 本仓库 `report.py` + 可选 LLM | 需要可视化工作流时接 Dify |
| 监测 | 暂不做 | 验证付费意愿后接 elmo |

**为什么第一版不直接 fork：** 这些仓库的技术栈（TypeScript/Next.js/Go/Python）各不相同，
现在就全部拉起 = 4 套部署 + 4 套认证，违反"禁止过度工程化"。
先用自家规则引擎跑通闭环，**验证有人愿意付钱后，再按层替换**。

## 4. 每层替换时的接口契约

因为模块边界已经画好，替换时只改一个文件：

- 换抓取 → 重写 `mandapi_geo/fetcher.py`，保持 `fetch_page() -> FetchResult` 签名
- 换 SEO → 重写 `analyzers/seo.py`，返回 `(list[Check], list[Issue])`
- 换 GEO → 重写 `analyzers/geo.py`，同上
- 换报告 → 重写 `report.py` 的 `generate()`

## 5. 尽调清单（引入任何新仓库前必须过）

1. `license` 字段非 null，且是 MIT / Apache-2.0 / BSD
2. 最后推送 < 6 个月
3. Stars > 50，或有明确的商业支持
4. 读一遍 LICENSE，确认有 patent grant（Apache-2.0 有，MIT 无）
5. 记录 `owner/repo@commit_sha`，锁定版本