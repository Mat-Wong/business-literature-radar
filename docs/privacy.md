# 隐私与安全 / Privacy and security

## 中文

- 软件在本机启动网页，服务器仅监听 `127.0.0.1`，不是公开托管的网站。不要通过端口转发、反向代理或防火墙规则把它暴露到互联网。
- 检索词会发送到用户选择的公开学术元数据服务。启用 LLM 时，研究问题、检索计划、候选论文元数据和需要翻译的摘要可能发送给用户自己选择的服务商。请遵守所在机构的数据使用政策，勿输入未获准分享的敏感资料。
- API Key 保存在本机用户配置中：Windows 路径为 `%APPDATA%\BusinessLiteratureRadar\settings.json`；macOS/Linux 默认为 `~/.config/BusinessLiteratureRadar/settings.json`（可由 `XDG_CONFIG_HOME` 改变）。Windows 优先使用当前用户的 DPAPI 保护；如果 DPAPI 不可用，以及在 macOS/Linux 上，文件采用 Base64 编码而非加密（非 Windows 会限制为当前用户可读）。请把它当作敏感文件，不要提交到 Git、分享整个配置文件夹或发送含 Key 的截图。多人共用电脑请使用独立系统账户。
- Codex CLI 模式依赖用户已经在本机登录的 Codex；软件不会复制其登录凭据。Claude 订阅不作为第三方网页应用的模型后端；订阅用户可在 Claude Code 中使用仓库内的原生 Skill。API Key 与订阅额度并不通用。
- 论文元数据、摘要和 LLM 译文均需人工核验。此工具不是系统综述质量评价、版权许可或全文获取的替代品。
- 停止检索可能留下部分输出文件；软件不会自动上传本地结果。

## English

- The app serves its web interface on `127.0.0.1` on your own computer. Do not expose that port through forwarding, a reverse proxy, or firewall rules.
- Search queries go to the selected public scholarly metadata services. If you enable an LLM, your research question, plan, candidate metadata, and abstracts to translate may be sent to your chosen model provider. Follow your institution's data-use rules and avoid entering sensitive material you are not permitted to share.
- API keys are saved in per-user local configuration: `%APPDATA%\BusinessLiteratureRadar\settings.json` on Windows, or `~/.config/BusinessLiteratureRadar/settings.json` on macOS/Linux (overridable with `XDG_CONFIG_HOME`). Windows prefers user-bound DPAPI protection. If DPAPI is unavailable, and on macOS/Linux, Base64 encoding is used instead of encryption (with owner-only permissions on non-Windows). Treat this as a sensitive file: do not commit or share it or screenshots containing a key. Use separate OS accounts on shared computers.
- Codex CLI mode uses your existing local Codex login without copying its credentials. A Claude subscription is not offered as the backend for this third-party web app; subscription users can use the native Claude Code Skill in the repository. API billing and subscription allowances are separate.
- Verify metadata, abstracts, and generated translations against the original papers. This tool is not a substitute for systematic-review quality assessment, copyright permission, or full-text access.
- Stopping a search may leave partial output. The app does not automatically upload locally generated reports.
