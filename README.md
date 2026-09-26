# 📡 商科文献雷达 — Business Literature Radar

**给商学院 PhD 和硕博研究者用的文献检索工具。** 输入研究问题，选择专业与期刊，找论文、看摘要、筛选结果，再根据反馈继续检索。

这是 [商科 PhD 科研 Skill](https://github.com/Mat-Wong/Business-Academic-Skill) 的配套项目：**雷达负责找文献，科研 Skill 帮你读文献、做研究、写论文。** 可以在本机网页中使用，也可以交给 Codex 或 Claude Code。

[English](README.en.md) · [下载 Windows 版](https://github.com/Mat-Wong/business-literature-radar/releases/latest) · [问题反馈](https://github.com/Mat-Wong/business-literature-radar/issues)

![商科文献雷达界面](docs/screenshot.png)

## 📌 一句话

**把一个研究问题，变成一份可以继续阅读和筛选的文献清单。**

## 🎯 能帮你做什么？

| 找文献时的麻烦 | 雷达的做法 |
|---|---|
| 有研究问题，但还没想好英文关键词 | 生成检索计划，关键词可以自己修改 |
| 搜出很多论文，想先看本专业的期刊 | 按专业选择 UTD24 期刊，也可逐本勾选 |
| 第一轮结果不太对，又要重新组织检索式 | 标记相关与不相关的论文，再做第二轮检索 |
| 想快速读懂英文标题和摘要 | 保留原文，并列显示中文译文 |
| 文献散在不同页面，不方便保存 | 导出 HTML、Markdown、CSV 和 JSON |

网页与 HTML 报告都支持中英文切换。检索时有进度显示，可以停止；完成后会提醒。

## 📚 专业与文献范围

适配商学院常见研究方向：**Fin、Acc、Mkt、OM、OR、IS、Mgmt、Econ、Strategy**。跨方向选题可以同时选择多个专业。

### UTD24 期刊

可以按专业选择，也可以直接勾选想检索的期刊。以下分组便于查找，不限制交叉研究：

| 方向 | 期刊 |
|---|---|
| Accounting | The Accounting Review；Journal of Accounting and Economics；Journal of Accounting Research |
| Finance | Journal of Finance；Journal of Financial Economics；Review of Financial Studies |
| Marketing | Journal of Marketing；Journal of Marketing Research；Marketing Science；Journal of Consumer Research |
| IS | Information Systems Research；INFORMS Journal on Computing；MIS Quarterly |
| OM / OR | Management Science；Operations Research；Journal of Operations Management；Manufacturing & Service Operations Management；Production and Operations Management |
| Management / Strategy | Academy of Management Journal；Academy of Management Review；Administrative Science Quarterly；Organization Science；Strategic Management Journal；Journal of International Business Studies |

期刊名单以 [UT Dallas 官方 UTD24 清单](https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/list-of-journals) 为准。**Econ 是可选研究方向，UTD24 本身不是经济学顶刊清单。**

### arXiv 与 SSRN

也可加入 **arXiv** 和 **SSRN**，查找预印本、工作论文及交叉学科研究。

目前检索论文题录、摘要和原始链接，不下载 PDF 全文。部分论文没有公开摘要；结果适合发现与初筛文献，正式引用前仍需阅读原文。

## 🚀 下载与使用

### Windows

1. 从 [最新版本](https://github.com/Mat-Wong/business-literature-radar/releases/latest) 下载 `business-literature-radar-v*-windows.zip`，解压。
2. 双击 `run.bat`，浏览器会打开本机网页。无需安装 Python。
3. 在设置里选择模型，输入自己的 API Key；已经登录 Codex 的用户也可选择本机 Codex。设置会保存在本地，下次不用重新填写。

不配置模型也能用规则模式做基础检索，但不能生成中文译文。

### 开始检索

1. **写研究问题**：中英文都可以，补充年份、专业、期刊和排除条件。
2. **确认检索计划**：检查关键词和范围，按需要修改，再开始检索。
3. **筛选首轮结果**：标记“相关 / 不相关 / 不确定”，继续第二轮检索。
4. **保存报告**：结果保存在程序目录的 `output/` 中，也可从网页打开。

例如：

> 检索 2020 年以来关于生成式 AI 如何影响消费者决策的研究，以 Marketing 期刊和 SSRN 为主。保留实验研究，排除纯技术模型论文，标题和摘要需要中文翻译。

勾选翻译后，会处理所有展示论文的标题和已有摘要。没有原始摘要或模型调用未成功的条目会注明，便于补查。

### macOS / Linux

需要 Python 3.10+：

```bash
git clone https://github.com/Mat-Wong/business-literature-radar.git
cd business-literature-radar
python3 app.py
```

也可在源码目录执行 `sh run.sh`。Windows 源码用户可执行 `python app.py`。

## 🤖 模型怎么选？

| 方式 | 使用方法 |
|---|---|
| OpenAI / Claude API | 在网页设置中填写自己的 Key |
| 其他兼容 API | 填写服务商的接口地址、模型名和 Key |
| 本机 Codex | 先安装并登录 Codex，再在网页中选择 |
| Codex / Claude Code Skill | 在对应工具中打开项目，用 Skill 完成检索、筛选与翻译 |
| OpenCode / Gemini CLI | 在高级设置中选择已安装并登录的本机工具 |

**API 按服务商计费；Codex / Claude Code Skills 使用已登录账户，受账户额度限制。** ChatGPT 或 Claude 订阅与 API 额度是两回事。

应用在本机运行，模型设置保存在本地。研究内容会发送给你选择的模型服务，详见[隐私说明](docs/privacy.md)。

## 🧩 Codex / Claude Code Skill

下载项目，在 Codex 或 Claude Code 中打开项目文件夹，然后直接说：

```text
使用 business-literature-radar Skill，检索供应链韧性与企业绩效的文献。
范围是 2018—2026 年的 OM / OR 和 Strategy 期刊，加上 SSRN。
先展示检索计划，筛选首轮结果后继续检索，最后给我带中文译文的报告。
```

两份 Skill 已放在各自的项目目录，无需另外填写本产品的 API Key：

```text
.agents/skills/business-literature-radar/   # Codex
.claude/skills/business-literature-radar/    # Claude Code
```

Skill 使用同一套检索引擎，由 Codex 或 Claude Code 负责规划、判断相关性和翻译。Windows 下载包自带引擎；其他系统使用 Python 源码。

## 开发与反馈

源码运行仅需 Python 标准库。不联网自检：

```bash
python search_papers.py --self-test
```

打包与开发说明见[构建文档](docs/build.md)，检索实现见[数据来源说明](docs/sources.md)。

欢迎在 [Issues](https://github.com/Mat-Wong/business-literature-radar/issues) 提建议、报问题。贴错误信息前，请删去 API Key 和私人研究内容。

**MIT 开源 · Mat-Wong**。如果有用，欢迎 Star，也欢迎一起改进。
