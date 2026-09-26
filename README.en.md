# 📡 Business Literature Radar

**A literature search tool for business-school PhD and graduate researchers.** Enter a research question, choose disciplines and journals, read abstracts, screen results, and search again with your feedback.

A companion to the [Bschool PhD Research Skill Suite](https://github.com/Mat-Wong/Business-Academic-Skill): **Radar finds papers; the Skill Suite helps you read them, develop research, and write.** Use a local web app or work directly in Codex or Claude Code.

[中文](README.md) · [Download for Windows](https://github.com/Mat-Wong/business-literature-radar/releases/latest) · [Feedback](https://github.com/Mat-Wong/business-literature-radar/issues)

![Business Literature Radar interface](docs/screenshot.png)

## 📌 In one sentence

**Turn a research question into a reading list you can review and refine.**

## 🎯 What does it help with?

| Search problem | What Radar does |
|---|---|
| You have a question but need better search terms | Drafts a plan with keywords you can edit |
| You want papers from journals in your discipline | Lets you select UTD24 journals by discipline or individually |
| The first results miss the point | Uses relevant / irrelevant feedback for a second round |
| You want Chinese versions of English titles and abstracts | Shows translations alongside the originals |
| Your reading list is scattered across pages | Exports HTML, Markdown, CSV, and JSON |

Both the web interface and HTML reports switch between Chinese and English. Searches show progress, can be stopped, and notify you when finished.

## 📚 Disciplines and sources

Designed for common business-school research areas: **Fin, Acc, Mkt, OM, OR, IS, Mgmt, Econ, and Strategy**. Select more than one for interdisciplinary questions.

### UTD24 journals

Select a discipline or pick individual journals. These groups are for navigation, not limits on interdisciplinary work:

| Area | Journals |
|---|---|
| Accounting | The Accounting Review; Journal of Accounting and Economics; Journal of Accounting Research |
| Finance | Journal of Finance; Journal of Financial Economics; Review of Financial Studies |
| Marketing | Journal of Marketing; Journal of Marketing Research; Marketing Science; Journal of Consumer Research |
| IS | Information Systems Research; INFORMS Journal on Computing; MIS Quarterly |
| OM / OR | Management Science; Operations Research; Journal of Operations Management; Manufacturing & Service Operations Management; Production and Operations Management |
| Management / Strategy | Academy of Management Journal; Academy of Management Review; Administrative Science Quarterly; Organization Science; Strategic Management Journal; Journal of International Business Studies |

The journal list follows the [official UT Dallas UTD24 list](https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/list-of-journals). **Econ is a research-area option; UTD24 is not a list of leading economics journals.**

### arXiv and SSRN

Add **arXiv** and **SSRN** to find preprints, working papers, and interdisciplinary research.

The current version retrieves paper records, abstracts, and original links, not full-text PDFs. Some papers have no public abstract. Use the results to discover and screen papers, and read the originals before citing them.

## 🚀 Download and use

### Windows

1. Download `business-literature-radar-v*-windows.zip` from the [latest release](https://github.com/Mat-Wong/business-literature-radar/releases/latest) and extract it.
2. Double-click `run.bat` to open the local web app. No Python installation is needed.
3. Choose a model in Settings and enter your API key, or select Codex if it is already installed and signed in. Your settings are saved locally for next time.

Rules mode supports basic search without model setup, but does not produce Chinese translations.

### Start a search

1. **Describe your question** in Chinese or English, with years, disciplines, journals, and exclusions.
2. **Review the search plan** and edit keywords or scope before searching.
3. **Screen round one** as relevant, irrelevant, or uncertain, then run a second round.
4. **Save the report** under `output/` beside the app, or open it from the web interface.

For example:

> Find research since 2020 on how generative AI affects consumer decisions. Focus on Marketing journals and SSRN, include experimental studies, exclude purely technical model papers, and translate titles and abstracts into Chinese.

When translation is enabled, every displayed title and available abstract is processed. Missing abstracts or unsuccessful translations are marked so you can follow up.

### macOS / Linux

Python 3.10+ is required:

```bash
git clone https://github.com/Mat-Wong/business-literature-radar.git
cd business-literature-radar
python3 app.py
```

You can also run `sh run.sh` from the source folder. On Windows, source users can run `python app.py`.

## 🤖 Choose a model

| Option | Setup |
|---|---|
| OpenAI / Claude API | Enter your own key in web Settings |
| Other compatible APIs | Enter the provider's endpoint, model name, and key |
| Local Codex | Install and sign in to Codex, then select it in the web app |
| Codex / Claude Code Skill | Open the project in the tool and use the Skill to search, screen, and translate |
| OpenCode / Gemini CLI | Select an installed, authenticated local tool in advanced settings |

**API usage is billed by your provider. Codex / Claude Code Skills use your signed-in account and are subject to its limits.** A ChatGPT or Claude subscription is separate from API credit.

The app runs locally and saves model settings on your computer. Research content is sent to the model service you select; see the [privacy notes](docs/privacy.md).

## 🧩 Codex / Claude Code Skill

Download the project, open its folder in Codex or Claude Code, and ask:

```text
Use the business-literature-radar Skill to find papers on supply-chain resilience
and firm performance. Search OM / OR and Strategy journals plus SSRN, 2018–2026.
Show the plan first, screen the initial results, run a second search round,
and give me a report with Chinese translations.
```

Both project-local Skills are included. No separate API key needs to be entered into Radar:

```text
.agents/skills/business-literature-radar/   # Codex
.claude/skills/business-literature-radar/    # Claude Code
```

The Skills use the same search engine, with Codex or Claude Code handling planning, relevance judgments, and translation. The Windows download includes the engine executable; other systems use the Python source.

## Development and feedback

The source uses only the Python standard library at runtime. Run the offline check:

```bash
python search_papers.py --self-test
```

See the [build guide](docs/build.md) for development and packaging, and the [source notes](docs/sources.md) for retrieval details.

Suggestions and bug reports are welcome in [Issues](https://github.com/Mat-Wong/business-literature-radar/issues). Remove API keys and private research content before sharing logs.

**MIT licensed · Mat-Wong.** If it helps your research, give it a Star or help improve it.
