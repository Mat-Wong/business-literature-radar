# Business Literature Radar

**Business Literature Radar** is a local research workbench for business-school PhD and graduate researchers. It turns a natural-language question into an editable search plan, gathers public paper metadata and abstracts, supports relevance feedback and a second search round, and opens a bilingual web interface on your own computer. No account with this project is required.

[中文说明](README.md) · [Privacy and security](docs/privacy.md) · [MIT License](LICENSE)

![Local web interface with search planning, progress, and reading desk](docs/screenshot.png)

The screenshot shows a live run using public OpenAlex metadata. Verify paper details at their original sources.

## Choose a way to use it

| Mode | Best for | Model access |
|---|---|---|
| Local web app + rules | Trying basic search without model setup | No LLM calls; limited planning, ranking, and translation |
| Local web app + your API key | Planning, reranking, and translation in the browser | Your OpenAI, Anthropic Claude, or compatible API; provider billing applies |
| Local web app + Codex CLI | People already signed in to Codex locally | Your local Codex CLI, subject to account eligibility and usage limits |
| Native Codex / Claude Code Skills | A complete workflow inside an agent | The agent's own model handles planning, screening, and translation; no separate key is required by this project |

The download does not contain the author's private API key. It also does not route a Claude subscription through a third-party web app. Claude Pro/Max subscribers can use the native Claude Code Skill; using Claude in the web app requires your own Claude API key. [OpenAI separates ChatGPT and API billing](https://help.openai.com/en/articles/9039756), and [Anthropic directs products built for others to API-key authentication](https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account).

## Download and run

### Windows: unzip and double-click

1. Download the latest `business-literature-radar-v*-windows.zip` from [Releases](https://github.com/Mat-Wong/business-literature-radar/releases) and extract it to a writable folder (not directly under `Program Files`).
2. Double-click `run.bat`. It launches `BusinessLiteratureRadar.exe` and opens the local website in your default browser.
3. Keep the default rules mode for a first look, or enter your own API key in Settings, or select an already authenticated Codex CLI.
4. Enter a research question, choose disciplines (which select target journals) and years, review the editable plan, then run the search.

The Windows archive includes the executable; Python is not required. Your OS or security software may ask whether to allow the program. The app connects to public scholarly metadata services and only to an LLM provider you select. Do not expose the local web port to the internet.

### macOS / Linux: run from source

Python 3.10+ is required. There are no extra runtime dependencies:

```bash
git clone https://github.com/Mat-Wong/business-literature-radar.git
cd business-literature-radar
python3 app.py
```

You may also run `sh run.sh` in a source checkout. On Windows, run `python app.py` or double-click `run.bat`. The server listens only on `127.0.0.1`; the console shows the address.

## A search from start to finish

1. Describe your question in Chinese or English. Optionally add inclusion and exclusion criteria. Pick a year range, result limit, and target business-school disciplines; the app maps those choices to journals. IS and QM are the defaults.
2. Review and edit the search plan, then start round one. The interface shows stages, progress, and logs, and lets you stop a running job.
3. Read the results, source links, and original abstracts. Mark first-round candidates relevant, irrelevant, or uncertain, then run the second search round. It uses the feedback to revise queries and can explore citation links from relevant seed papers.
4. Switch the interface and exported HTML report between 中文 and English. Original paper titles and abstracts remain intact; when translation is enabled, Chinese versions appear alongside them. Missing source abstracts and model-related translation gaps are indicated rather than silently filled.
5. Open the local HTML, Markdown, CSV, or JSON files under `output/` beside the app. Round two records feedback and a search audit.

The progress percentage reflects completed work stages, not an exact time-to-completion estimate. Stopping may leave partial files. A completion notification is shown only after a report is successfully generated. Closing the browser tab does not stop the local server; use the interface's Exit app button.

## Sources and verifiability

The engine aggregates public metadata from OpenAlex, Crossref, Semantic Scholar, arXiv, DBLP, and SSRN-related records, deduplicates papers using identifiers such as DOIs, and ranks candidates using topic, year, and selected target journals. Disciplines include IS, QM / Analytics, OM, Strategy, Finance, Accounting, Management / OB, Marketing, Business Economics, Econometrics / Statistics / Data Science, Behavioral Science, Political Economy / Public Policy, Health Care Management, and Ethics & Legal Studies. arXiv, SSRN, and CS/ML remain available as cross-disciplinary leads.

Coverage and abstract availability vary by source, and individual services may rate-limit or reject requests. Results support discovery and screening; they are not guaranteed exhaustive and cannot replace database searches, manual verification, or a systematic-review protocol. The current version does not download or parse full PDFs or bypass paywalls.

## Models and costs

Enter your model settings once. They are stored in a per-user `BusinessLiteratureRadar` directory separate from the author's personal edition. Keys are not distributed in GitHub source or Windows downloads and are not written to reports. See [Privacy and security](docs/privacy.md) for paths, protection, and data flows.

- **OpenAI API:** Create your own key on the [OpenAI API platform](https://platform.openai.com/api-keys) and check that the API account has available credit.
- **Claude API:** Create your own key in the [Claude Console](https://console.anthropic.com/settings/keys). A Claude subscription does not include Claude API allowance.
- **Compatible API:** Enter the full HTTPS endpoint, model names, and key from a provider you trust.
- **Codex CLI:** Install, sign in, and verify the local CLI using the [Codex non-interactive mode guide](https://learn.chatgpt.com/docs/non-interactive-mode). The app invokes your local CLI without reading its login credentials. Your account determines eligible models and limits.
- **OpenCode / Gemini CLI:** Preserved as advanced local CLI choices. Install and authenticate them yourself; compatibility may vary by version.
- **Rules mode:** No LLM calls. It supports basic search but does not invent Chinese translations.

When translation is enabled, the tool attempts Chinese titles and abstracts for every displayed paper, switching to configured fallback models when one fails. Provider limits, timeouts, or missing source data can still leave gaps, which the interface and report identify. Deep searches and complete translation can incur noticeable API charges; consider setting a spending cap at your provider.

## Codex and Claude Code Skills

The repository includes both native skills:

```text
.agents/skills/business-literature-radar/   # Codex
.claude/skills/business-literature-radar/    # Claude Code
```

Open this project in Codex or Claude Code and explicitly ask it to use the `business-literature-radar` Skill for your research question. The Skill calls the same local search engine, while the agent's own model handles planning, screening, translation, and report preparation; no API key has to be entered into this product. The Windows download includes an engine executable that the Skill can call; macOS/Linux use the Python source. Each agent's account, client, and model limits still apply. The Skill does not imply free subscriptions or unlimited usage. See [Codex Skills](https://learn.chatgpt.com/docs/build-skills) and [Claude Code Skills](https://code.claude.com/docs/en/skills) for native skill behavior.

The Skill bridge splits final papers into auditable translation batches. It writes separate `-agent` HTML/Markdown/CSV/JSON reports only after every paper has been covered, leaving the original search report intact.

## Repository map

```text
app.py                 Local web server and job control
web/                   Bilingual interface
search_papers.py       First-round search and reports
search_v2.py           Feedback-driven second round
agent_bridge.py        Bridge between native Skills and the engine
app_settings.py        Per-user settings
.agents/skills/         Codex Skill
.claude/skills/         Claude Code Skill
run.bat / run.sh       Launchers
build_windows.ps1      Windows packaging
```

The source uses only the Python standard library at runtime. Windows packaging uses PyInstaller. Developers can run this offline self-test:

```bash
python search_papers.py --self-test
```

See the [build guide](docs/build.md) for Windows packaging and automated releases.

## Feedback and license

Please report bugs or suggestions in [GitHub Issues](https://github.com/Mat-Wong/business-literature-radar/issues). Include OS/Python versions, non-sensitive error information, and reproduction steps. Do not paste API keys, private research data, or your local settings file. Released under the [MIT License](LICENSE). Created and maintained by Mat-Wong.
