/* Business Literature Radar — local-only, dependency-free client. */
(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const nodes = {
    query: $("#query-input"),
    from: $("#year-from"),
    to: $("#year-to"),
    limit: $("#limit-input"),
    disciplines: $("#discipline-options"),
    sources: $("#source-options"),
    translate: $("#translate-input"),
    searchForm: $("#search-form"),
    planButton: $("#plan-button"),
    searchButton: $("#search-button"),
    planSearchButton: $("#plan-search-button"),
    planPanel: $("#plan-panel"),
    planEnglish: $("#plan-english"),
    planSummary: $("#plan-summary"),
    planExpanded: $("#plan-expanded"),
    planMust: $("#plan-must"),
    planExclude: $("#plan-exclude"),
    jobBadge: $("#job-badge"),
    stage: $("#stage-text"),
    detail: $("#detail-text"),
    percent: $("#progress-percent"),
    progress: $("#progress-bar"),
    live: $("#live-status"),
    stop: $("#stop-button"),
    empty: $("#results-empty"),
    resultsContent: $("#results-content"),
    resultsList: $("#results-list"),
    resultsCount: $("#results-count"),
    deep: $("#deep-button"),
    report: $("#report-link"),
    connection: $("#connection-status"),
    lang: $("#language-button"),
    settingsButton: $("#settings-button"),
    settingsDialog: $("#settings-dialog"),
    settingsForm: $("#settings-form"),
    settingsClose: $("#settings-close"),
    settingsCancel: $("#settings-cancel"),
    desktopNotify: $("#desktop-notify-input"),
    exitButton: $("#exit-button"),
    settingsError: $("#settings-error"),
    apiFields: $("#api-fields"),
    provider: $("#provider-select"),
    providerLabel: document.querySelector('label[for="provider-select"]'),
    apiKeyField: $("#api-key-field"),
    apiEndpointField: $("#api-endpoint-field"),
    apiKey: $("#api-key-input"),
    apiEndpoint: $("#api-endpoint-input"),
    apiModels: $("#api-models-input"),
    keyHelp: $("#key-help"),
    backendNote: $("#backend-note"),
    toast: $("#toast"),
    toastText: $("#toast-text"),
    toastClose: $("#toast-close"),
    queryError: $("#query-error")
  };
  const I18N = {
    zh: {
      brand: "商科文献雷达", localOnly: "仅在本机运行", settings: "模型设置",
      workspace: "研究工作台", searchTitle: "从问题出发。", searchIntro: "写下你真正想找的文献。先查看检索计划，再开始搜索。",
      queryLabel: "研究问题", queryPlaceholder: "例如：生成式 AI 如何改变企业决策？", queryHelp: "可以用中文或英文，尽量写明情境与核心变量。",
      fromYear: "起始年份", toYear: "截止年份", limitLabel: "展示文献", disciplineLabel: "研究学科", sourceLabel: "文献来源",
      loadingOptions: "正在载入…", translateLabel: "同时生成中文译文", translateHelp: "展示的每篇文献都配有题名与摘要译文",
      previewPlan: "预览计划", startSearch: "开始检索", metadataNote: "只检索公开元数据、摘要和开放获取链接；不抓取付费全文。",
      currentTask: "当前任务", statusHeading: "检索进度", statusIdle: "等待开始", statusPlanning: "制定计划", statusRunning: "运行中",
      statusCompleted: "已完成", statusFailed: "失败", statusStopped: "已停止", statusStopping: "正在停止",
      readyStage: "准备好后，先预览检索计划。", readyDetail: "检索期间可在这里查看阶段与百分比。",
      idleFootnote: "尚未运行", stopSearch: "停止检索", planCaption: "搜索之前", planHeading: "检索计划",
      editablePlan: "可编辑后再运行", englishQuery: "英文检索式", planSummary: "检索思路",
      expandedQueries: "拓展关键词", mustTerms: "必须包含", excludeTerms: "排除术语",
      onePerLine: "每行一个", usePlan: "使用此计划检索", readingDesk: "阅读桌", resultsHeading: "文献结果",
      emptyTitle: "这里还没有文献。", emptyText: "输入研究问题，预览计划，然后开始检索。找到的题名、摘要与来源会在这里集中展示。",
      feedbackInstruction: "标记相关性，帮助第二轮检索聚焦。", deepSearch: "开始第二轮深搜", openReport: "打开完整报告 ↗",
      productName: "商科文献雷达", footerNote: "本地运行 · 文献数据请以原始来源为准",
      settingsCaption: "个人模型连接", settingsHeading: "选择你的模型入口",
      settingsIntro: "设置只保存在你的电脑上。公开版本不预置作者的私人密钥。",
      backendLabel: "运行方式", backendApi: "使用自己的 API Key", backendApiHint: "OpenAI、Claude 或兼容服务",
      backendCodex: "使用已登录的 Codex", backendCodexHint: "使用本机 Codex CLI 与你的订阅",
      backendAdvanced: "其他本机 CLI（高级）", backendAdvancedHint: "OpenCode 或 Gemini CLI，需自行安装登录",
      backendRules: "先不用模型", backendRulesHint: "规则检索；不支持模型翻译",
      providerLabel: "API 服务商", cliProviderLabel: "本机命令", apiKeyLabel: "API Key", savedKeyPlaceholder: "输入你的 API Key",
      keyLocal: "密钥保存在本机，不会出现在报告中。", keySaved: "本机已保存密钥；留空则继续使用。",
      advancedSettings: "高级设置", endpointLabel: "API 地址", modelsLabel: "模型顺序",
      modelsPlaceholder: "用英文逗号分隔多个模型", modelsHelp: "额度不足时会按此顺序尝试其他模型。",
      cancel: "取消", saveSettings: "保存设置", desktopNotify: "检索完成时发送桌面提醒",
      desktopNotifyHelp: "需要浏览器通知权限，可随时关闭。",
      codexNote: "请先在本机安装并登录 Codex CLI。网页不会读取或保存你的 Codex 凭据。",
      advancedNote: "OpenCode / Gemini CLI 需先在本机安装并登录；不同版本的命令行兼容性可能不同。",
      rulesNote: "规则模式无需密钥，可检索公开文献。中文翻译需要 API 或 Codex。",
      apiNote: "Claude Pro/Max 订阅请在 Claude Code Skill 内使用；网页中的 Claude 入口需你自己的 API Key。",
      needQuery: "请先写下研究问题。", invalidYears: "年份范围不正确，请检查起止年份。",
      needDiscipline: "至少选择一个研究学科。", needSource: "至少选择一个文献来源。",
      apiRequired: "尚未保存 API Key，请在模型设置中填入自己的密钥。",
      noTranslateRules: "规则模式不能生成译文。请切换到 API 或本机 CLI，或关闭中文翻译。",
      requestFailed: "请求未完成，请检查本地服务并重试。", disconnected: "本地服务暂时无法连接。",
      planReady: "计划已准备好，可检查关键词并开始检索。", searchReady: "文献检索完成。", deepReady: "第二轮深搜完成。",
      searchFailed: "检索未完成。", stopped: "检索已停止。", stopping: "正在安全停止…",
      runningDetail: "正在处理，请稍候。", completionToast: "检索完成，文献已在阅读桌中。", planToast: "检索计划已生成。",
      deepToast: "第二轮深搜完成，结果已更新。", count: "篇文献", abstract: "查看摘要", abstractOriginal: "原文摘要",
      abstractTranslation: "中文摘要", missingAbstract: "来源未提供摘要。", source: "来源", year: "年份", score: "相关分",
      feedbackLabel: "相关性", relevant: "相关", irrelevant: "不相关", uncertain: "待定",
      paperLink: "打开文献原始来源", noResults: "本次未找到可展示的文献，请调整问题或年份重试。",
      needFeedback: "请先标记至少一篇“相关”或“不相关”的文献。",
      deepAlready: "第二轮深搜已经完成。", saveFailed: "设置未保存，请检查输入后重试。",
      notificationDenied: "浏览器未允许桌面通知；仍会通过页面提醒。",
      browserTitle: "商科文献雷达", browserTitleDone: "检索完成 · 商科文献雷达",
      noLink: "暂无来源链接", loading: "处理中…", optionsFailed: "未能载入选项，请刷新页面。",
      settingsSaved: "设置已保存。", noneSelected: "未选择", unknown: "未提供",
      reason: "相关性说明", expandPaper: "展开摘要", collapsePaper: "收起摘要",
      reportUnavailable: "报告尚未生成。", exitApp: "退出应用", exitHelp: "停止本机服务后即可关闭此标签页。",
      appClosed: "本机服务已停止，可以关闭此标签页。"
    },
    en: {
      brand: "Literature Radar", localOnly: "Running on this device", settings: "Model settings",
      workspace: "Research workbench", searchTitle: "Start with your question.", searchIntro: "Describe the literature you need. Review the search plan before running it.",
      queryLabel: "Research question", queryPlaceholder: "e.g. How does generative AI change firm decisions?", queryHelp: "Write in English or Chinese; name the setting and key concepts.",
      fromYear: "From year", toYear: "Through year", limitLabel: "Papers to show", disciplineLabel: "Disciplines", sourceLabel: "Sources",
      loadingOptions: "Loading…", translateLabel: "Add Chinese translations", translateHelp: "Translate titles and abstracts for every displayed paper",
      previewPlan: "Preview plan", startSearch: "Start search", metadataNote: "Searches public metadata, abstracts and open-access links; does not retrieve paywalled full text.",
      currentTask: "Current task", statusHeading: "Search progress", statusIdle: "Ready", statusPlanning: "Planning", statusRunning: "Running",
      statusCompleted: "Complete", statusFailed: "Failed", statusStopped: "Stopped", statusStopping: "Stopping",
      readyStage: "Preview a search plan when you are ready.", readyDetail: "Stages and percentages will appear here while a search runs.",
      idleFootnote: "No task running", stopSearch: "Stop search", planCaption: "Before the search", planHeading: "Search plan",
      editablePlan: "Edit before running", englishQuery: "English search query", planSummary: "Search approach",
      expandedQueries: "Expanded queries", mustTerms: "Required terms", excludeTerms: "Exclude terms",
      onePerLine: "One per line", usePlan: "Search with this plan", readingDesk: "Reading desk", resultsHeading: "Papers",
      emptyTitle: "No papers here yet.", emptyText: "Enter a research question, preview the plan, then start a search. Titles, abstracts and sources will appear here.",
      feedbackInstruction: "Mark relevance to focus the second search round.", deepSearch: "Run second-round search", openReport: "Open full report ↗",
      productName: "Literature Radar", footerNote: "Runs locally · Verify bibliographic details at their source",
      settingsCaption: "Your model connection", settingsHeading: "Choose a model route",
      settingsIntro: "Settings stay on your computer. This public edition contains no private author key.",
      backendLabel: "Run with", backendApi: "Your own API key", backendApiHint: "OpenAI, Claude or a compatible service",
      backendCodex: "Signed-in Codex", backendCodexHint: "Uses local Codex CLI and your subscription",
      backendAdvanced: "Other local CLI (advanced)", backendAdvancedHint: "OpenCode or Gemini CLI; install and sign in yourself",
      backendRules: "No model for now", backendRulesHint: "Rule-based search; no model translation",
      providerLabel: "API provider", cliProviderLabel: "Local command", apiKeyLabel: "API key", savedKeyPlaceholder: "Enter your API key",
      keyLocal: "The key stays on this device and is never placed in a report.", keySaved: "A key is saved on this device; leave blank to keep it.",
      advancedSettings: "Advanced settings", endpointLabel: "API endpoint", modelsLabel: "Model order",
      modelsPlaceholder: "Separate models with commas", modelsHelp: "If one model is unavailable, the next is tried.",
      cancel: "Cancel", saveSettings: "Save settings", desktopNotify: "Send a desktop notification when done",
      desktopNotifyHelp: "Requires browser permission; you can turn it off anytime.",
      codexNote: "Install and sign in to Codex CLI on this device first. The page does not read or save Codex credentials.",
      advancedNote: "Install and sign in to OpenCode or Gemini CLI first. Command compatibility may vary by version.",
      rulesNote: "Rule mode needs no key and can search public papers. Chinese translation requires an API or Codex.",
      apiNote: "Use a Claude Pro/Max subscription through the Claude Code Skill; the web app needs your own Claude API key.",
      needQuery: "Write a research question before continuing.", invalidYears: "The year range is invalid; check the start and end years.",
      needDiscipline: "Select at least one discipline.", needSource: "Select at least one source.",
      apiRequired: "No API key is saved. Open model settings and enter your own key.",
      noTranslateRules: "Rule mode cannot translate. Switch to an API or local CLI, or turn off translations.",
      requestFailed: "The request did not finish. Check the local service and retry.", disconnected: "The local service is unavailable.",
      planReady: "The plan is ready. Review its terms and start the search.", searchReady: "Literature search complete.", deepReady: "Second-round search complete.",
      searchFailed: "The search did not finish.", stopped: "The search has stopped.", stopping: "Stopping safely…",
      runningDetail: "Working through the search. Please wait.", completionToast: "Search complete. Papers are on your reading desk.", planToast: "Search plan ready.",
      deepToast: "Second-round search complete. Results updated.", count: "papers", abstract: "Read abstract", abstractOriginal: "Original abstract",
      abstractTranslation: "Chinese translation", missingAbstract: "No abstract was provided by this source.", source: "Source", year: "Year", score: "Relevance",
      feedbackLabel: "Relevance", relevant: "Relevant", irrelevant: "Not relevant", uncertain: "Unsure",
      paperLink: "Open original paper source", noResults: "No displayable papers were found. Adjust your question or year range and retry.",
      needFeedback: "Mark at least one paper as “Relevant” or “Not relevant” first.",
      deepAlready: "The second search round is already complete.", saveFailed: "Settings were not saved. Check the fields and retry.",
      notificationDenied: "Desktop notifications were not allowed; in-page alerts will still appear.",
      browserTitle: "Business Literature Radar", browserTitleDone: "Search complete · Literature Radar",
      noLink: "No source link", loading: "Working…", optionsFailed: "Options could not load; refresh the page.",
      settingsSaved: "Settings saved.", noneSelected: "None selected", unknown: "Not provided",
      reason: "Why this paper", expandPaper: "Expand abstract", collapsePaper: "Collapse abstract",
      reportUnavailable: "The report is not ready yet.", exitApp: "Exit app", exitHelp: "Stop the local service, then close this tab.",
      appClosed: "The local service has stopped. You can close this tab."
    }
  };

  const sessionToken = $('meta[name="session-token"]').content;
  const client = {
    lang: localStorage.getItem("radar-language") === "en" ? "en" : "zh",
    notifyDesktop: localStorage.getItem("radar-desktop-notify") === "yes",
    config: {},
    meta: {},
    job: null,
    plan: null,
    rows: [],
    feedback: new Map(),
    firstStateSeen: false,
    lastCompletedId: null,
    lastJobSignature: "",
    wasRunning: false,
    polling: false,
    toastTimer: null,
    titleTimer: null,
    online: true
  };
  const t = (key) => I18N[client.lang][key] || key;
  const canUseUrl = (value) => {
    try {
      if (!value) return false;
      const parsed = new URL(String(value), window.location.href);
      return parsed.protocol === "http:" || parsed.protocol === "https:";
    } catch {
      return false;
    }
  };
  const safeReportUrl = (value) => {
    const v = String(value || "");
    try {
      const parsed = new URL(v, window.location.origin);
      return parsed.origin === window.location.origin && parsed.pathname.startsWith("/reports/") &&
        !parsed.pathname.split("/").includes("..") && /\.(html|json)$/.test(parsed.pathname) ? v : "";
    } catch { return ""; }
  };
  const numberValue = (value, fallback) => {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  };
  const isRunning = (status) => ["pending", "queued", "starting", "running", "stopping", "cancelling"].includes(String(status || "").toLowerCase());
  const isComplete = (status) => ["completed", "complete", "done", "success"].includes(String(status || "").toLowerCase());
  const isFailed = (status) => ["failed", "error"].includes(String(status || "").toLowerCase());
  const isStopped = (status) => ["stopped", "cancelled", "canceled"].includes(String(status || "").toLowerCase());
  const jobKind = (job) => String((job && job.kind) || "").toLowerCase();
  const isPlanJob = (job) => jobKind(job).includes("plan");
  const isDeepJob = (job) => jobKind(job).includes("deep") || jobKind(job).includes("v2");

  async function api(path, method = "GET", body) {
    const options = { method, cache: "no-store", credentials: "same-origin", headers: { Accept: "application/json" } };
    if (method !== "GET") {
      options.headers["Content-Type"] = "application/json";
      options.headers["X-Session-Token"] = sessionToken;
      options.body = JSON.stringify(body || {});
    }
    const response = await fetch(path, options);
    let data = {};
    try { data = await response.json(); } catch { /* Let status explain non-JSON errors. */ }
    if (!response.ok) {
      const message = typeof data.error === "string" ? data.error : (typeof data.message === "string" ? data.message : t("requestFailed"));
      throw new Error(message);
    }
    return data;
  }

  function translateDom() {
    document.documentElement.lang = client.lang === "zh" ? "zh-CN" : "en";
    document.title = t("browserTitle");
    document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => { node.placeholder = t(node.dataset.i18nPlaceholder); });
    nodes.lang.textContent = client.lang === "zh" ? "EN" : "中文";
    nodes.lang.setAttribute("aria-label", client.lang === "zh" ? "Switch to English" : "切换为中文");
    renderMeta();
    renderConfig();
    renderJob(client.job);
    renderResults();
  }

  function choiceNodes(container, values, selected) {
    container.replaceChildren();
    (values || []).forEach((item) => {
      const id = typeof item === "string" ? item : item.id;
      if (!id) return;
      const label = document.createElement("label");
      label.className = "choice-chip";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = id;
      input.checked = selected.includes(id);
      const span = document.createElement("span");
      span.textContent = typeof item === "string" ? item : (client.lang === "zh" ? item.label_zh : item.label_en) || id;
      label.append(input, span);
      container.append(label);
    });
  }

  function renderMeta() {
    if (!client.meta.disciplines) return;
    const picked = (container, fallback) => {
      const checkboxes = [...container.querySelectorAll("input:checked")].map((input) => input.value);
      return container.querySelector("input") ? checkboxes : fallback;
    };
    choiceNodes(nodes.disciplines, client.meta.disciplines, picked(nodes.disciplines, ["is", "qm"]));
    choiceNodes(nodes.sources, client.meta.sources, picked(nodes.sources, ["openalex", "crossref", "semantic_scholar"]));
    renderProviders();
  }

  function renderProviders() {
    const mode = selectedBackend();
    const previous = nodes.provider.value || client.config.provider || "openai";
    const allowed = mode === "advanced" ? ["opencode", "gemini_cli"] : ["openai", "anthropic", "openai_compatible"];
    nodes.provider.replaceChildren();
    (client.meta.providers || []).filter((provider) => allowed.includes(provider.id)).forEach((provider) => {
      const option = document.createElement("option");
      option.value = provider.id;
      option.textContent = (client.lang === "zh" ? provider.label_zh : provider.label_en) || provider.id;
      nodes.provider.append(option);
    });
    if (allowed.includes(previous)) nodes.provider.value = previous;
    else if (allowed.includes(client.config.provider)) nodes.provider.value = client.config.provider;
  }

  function selectedBackend() {
    return document.querySelector('input[name="llm-backend"]:checked')?.value || "rules";
  }

  function updateBackendFields() {
    const mode = selectedBackend();
    const oldProvider = nodes.provider.value;
    renderProviders();
    if (nodes.provider.value !== oldProvider) {
      const preset = (client.meta.providers || []).find((item) => item.id === nodes.provider.value);
      nodes.apiEndpoint.value = preset?.endpoint || "";
      nodes.apiModels.value = preset?.models || "";
    }
    nodes.apiFields.hidden = !["api", "advanced"].includes(mode);
    nodes.apiKeyField.hidden = mode !== "api";
    nodes.apiEndpointField.hidden = mode !== "api";
    nodes.providerLabel.textContent = t(mode === "advanced" ? "cliProviderLabel" : "providerLabel");
    nodes.backendNote.textContent = t(mode === "api" ? "apiNote" : mode === "codex" ? "codexNote" : mode === "advanced" ? "advancedNote" : "rulesNote");
  }

  function renderConfig() {
    const mode = client.config.llm_backend || "rules";
    const radio = document.querySelector(`input[name="llm-backend"][value="${mode}"]`);
    if (radio) radio.checked = true;
    if (client.config.provider && nodes.provider.querySelector(`option[value="${client.config.provider}"]`)) nodes.provider.value = client.config.provider;
    updateBackendFields();
    nodes.keyHelp.textContent = client.config.has_key ? t("keySaved") : t("keyLocal");
    const preset = (client.meta.providers || []).find((item) => item.id === nodes.provider.value);
    if (document.activeElement !== nodes.apiEndpoint) nodes.apiEndpoint.value = client.config.api_endpoint || preset?.endpoint || "";
    if (document.activeElement !== nodes.apiModels) nodes.apiModels.value = client.config.api_models || preset?.models || "";
    nodes.desktopNotify.checked = client.notifyDesktop;
  }

  function editedPlan() {
    if (!client.plan) return null;
    const lines = (value) => value.split(/\r?\n/).map((part) => part.trim()).filter(Boolean);
    return {
      ...client.plan,
      english_query: nodes.planEnglish.value.trim(),
      summary: nodes.planSummary.value.trim(),
      expanded_queries: lines(nodes.planExpanded.value),
      must_have_terms: lines(nodes.planMust.value),
      exclude_terms: lines(nodes.planExclude.value)
    };
  }

  function renderPlan(plan) {
    if (!plan || typeof plan !== "object") return;
    client.plan = plan;
    nodes.planPanel.hidden = false;
    nodes.planEnglish.value = String(plan.english_query || "");
    nodes.planSummary.value = String(plan.summary || "");
    nodes.planExpanded.value = (plan.expanded_queries || []).join("\n");
    nodes.planMust.value = (plan.must_have_terms || []).join("\n");
    nodes.planExclude.value = (plan.exclude_terms || []).join("\n");
  }

  function renderJob(job) {
    client.job = job || null;
    const status = String(job?.status || "").toLowerCase();
    const active = isRunning(status);
    const tone = isFailed(status) ? "error" : isComplete(status) ? "success" : active ? "active" : "";
    nodes.jobBadge.dataset.tone = tone;
    nodes.jobBadge.textContent = t(!job ? "statusIdle" : status === "stopping" ? "statusStopping" :
      isPlanJob(job) && active ? "statusPlanning" : active ? "statusRunning" :
      isComplete(status) ? "statusCompleted" : isFailed(status) ? "statusFailed" : "statusStopped");
    nodes.stop.hidden = !active || status === "stopping";
    nodes.planButton.disabled = active;
    nodes.searchButton.disabled = active;
    nodes.planSearchButton.disabled = active;
    nodes.deep.disabled = active || !client.rows.length || isDeepJob(job) || ![...client.feedback.values()].some((v) => v !== "uncertain");
    const percent = Math.max(0, Math.min(100, numberValue(job?.percent, 0)));
    nodes.percent.value = `${Math.round(percent)}%`;
    nodes.percent.textContent = `${Math.round(percent)}%`;
    nodes.progress.value = percent;
    const stage = client.lang === "zh" ? job?.stage_zh || job?.stage : job?.stage_en || job?.stage;
    const detail = client.lang === "zh" ? job?.detail_zh || job?.detail : job?.detail_en || job?.detail;
    nodes.stage.textContent = job ? (isFailed(status) ? t("searchFailed") : stage || t("runningDetail")) : t("readyStage");
    nodes.detail.textContent = job ? (isFailed(status) ? job.error || t("requestFailed") : detail || t("runningDetail")) : t("readyDetail");
    nodes.live.textContent = !job ? t("idleFootnote") : isComplete(status) ? t(isPlanJob(job) ? "planReady" : isDeepJob(job) ? "deepReady" : "searchReady") :
      isFailed(status) ? t("searchFailed") : isStopped(status) ? t("stopped") : status === "stopping" ? t("stopping") : t("loading");
  }

  function textElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = String(text ?? "");
    return element;
  }

  function renderResults() {
    const rows = client.rows;
    nodes.empty.hidden = rows.length > 0;
    nodes.resultsContent.hidden = rows.length === 0;
    nodes.resultsCount.textContent = rows.length ? `${rows.length} ${t("count")}` : "";
    const reportUrl = safeReportUrl(client.job?.report_url);
    nodes.report.hidden = !reportUrl;
    if (reportUrl) nodes.report.href = reportUrl;
    const signature = JSON.stringify([client.lang, client.job?.id, rows.map((row) => row.identity), [...client.feedback.entries()]]);
    if (client.renderedResultsSignature === signature) return;
    client.renderedResultsSignature = signature;
    nodes.resultsList.replaceChildren();
    rows.forEach((row, index) => {
      const li = document.createElement("li");
      li.className = "paper";
      const head = textElement("div", "paper-head", "");
      head.append(textElement("span", "paper-index", String(index + 1).padStart(2, "0")));
      const body = textElement("div", "paper-body", "");
      const title = textElement("h3", "paper-title", "");
      const sourceUrl = [row.url, row.doi ? `https://doi.org/${row.doi}` : "", row.pdf_url].find(canUseUrl);
      if (sourceUrl) {
        const link = textElement("a", "", row.title || t("unknown"));
        link.href = sourceUrl;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.setAttribute("aria-label", `${t("paperLink")}: ${row.title || ""}`);
        title.append(link);
      } else title.textContent = row.title || t("unknown");
      body.append(title);
      if (row.title_zh) body.append(textElement("p", "paper-title-zh", row.title_zh));
      const meta = textElement("div", "paper-meta", "");
      [row.year, row.venue, row.source, Number.isFinite(Number(row.score)) ? `${t("score")} ${Number(row.score).toFixed(1)}` : ""].filter(Boolean).forEach((v) => meta.append(textElement("span", "", v)));
      body.append(meta);
      if (row.abstract || row.abstract_zh) {
        const details = document.createElement("details");
        details.className = "paper-abstract";
        details.append(textElement("summary", "", t("abstract")));
        if (row.abstract_zh) details.append(textElement("p", "", `${t("abstractTranslation")} · ${row.abstract_zh}`));
        details.append(textElement("p", "", `${t("abstractOriginal")} · ${row.abstract || t("missingAbstract")}`));
        body.append(details);
      } else body.append(textElement("p", "paper-meta", t("missingAbstract")));
      const feedback = textElement("div", "paper-feedback", "");
      feedback.append(textElement("span", "paper-feedback__label", t("feedbackLabel")));
      ["relevant", "irrelevant", "uncertain"].forEach((label) => {
        const button = textElement("button", "feedback-button", t(label));
        button.type = "button";
        button.setAttribute("aria-pressed", client.feedback.get(row.identity) === label ? "true" : "false");
        button.addEventListener("click", async () => {
          client.feedback.set(row.identity, label);
          renderResults();
          try {
            await api("/api/feedback", "POST", { feedback: feedbackPayload() });
          } catch (error) { showToast(error.message, "error"); }
          renderJob(client.job);
        });
        feedback.append(button);
      });
      body.append(feedback);
      head.append(body);
      li.append(head);
      nodes.resultsList.append(li);
    });
    nodes.deep.disabled = isRunning(client.job?.status) || !rows.length || isDeepJob(client.job) || ![...client.feedback.values()].some((v) => v !== "uncertain");
  }

  function feedbackPayload() {
    return [...client.feedback.entries()].map(([key, label]) => ({ key, label }));
  }

  function showToast(message, tone = "normal") {
    nodes.toastText.textContent = String(message || "");
    nodes.toast.dataset.tone = tone;
    nodes.toast.hidden = false;
    clearTimeout(client.toastTimer);
    client.toastTimer = setTimeout(() => { nodes.toast.hidden = true; }, tone === "error" ? 9500 : 5500);
  }

  function completedNotification(job) {
    if (!job || isPlanJob(job) || client.lastCompletedId === job.id) return;
    client.lastCompletedId = job.id;
    showToast(t(isDeepJob(job) ? "deepToast" : "completionToast"));
    document.title = t("browserTitleDone");
    clearTimeout(client.titleTimer);
    client.titleTimer = setTimeout(() => { document.title = t("browserTitle"); }, 15000);
    if (client.notifyDesktop && "Notification" in window && Notification.permission === "granted") {
      new Notification(t("browserTitleDone"), { body: t(isDeepJob(job) ? "deepToast" : "completionToast") });
    }
  }

  async function syncState() {
    if (client.polling) return;
    client.polling = true;
    try {
      const state = await api("/api/state");
      client.online = true;
      client.config = state.config || {};
      const job = state.job || null;
      if (job?.query && !nodes.query.value.trim()) nodes.query.value = job.query;
      if (job?.years && /^\d{4}-\d{4}$/.test(job.years) && !client.restoredYears) {
        const [from, to] = job.years.split("-");
        nodes.from.value = from;
        nodes.to.value = to;
        client.restoredYears = true;
      }
      if (job?.limit && !client.restoredLimit) {
        if ([...nodes.limit.options].some((option) => Number(option.value) === Number(job.limit))) nodes.limit.value = job.limit;
        client.restoredLimit = true;
      }
      if (job && isPlanJob(job) && isComplete(job.status) && job.plan && client.lastJobSignature !== `${job.id}:plan`) {
        renderPlan(job.plan);
        client.lastJobSignature = `${job.id}:plan`;
      }
      if (job && !isPlanJob(job) && Array.isArray(job.results) && job.results.length) {
        if (client.lastJobSignature !== `${job.id}:results`) {
          client.rows = job.results;
          client.feedback.clear();
          client.lastJobSignature = `${job.id}:results`;
        }
      }
      if (Array.isArray(state.feedback) && state.feedback.length && client.feedback.size === 0) {
        state.feedback.forEach((item) => { if (item.key) client.feedback.set(item.key, item.state || item.label); });
      }
      if (!nodes.settingsDialog.open) renderConfig();
      renderJob(job);
      renderResults();
      if (client.firstStateSeen && job && isComplete(job.status)) completedNotification(job);
      if (job && isFailed(job.status) && client.lastCompletedId !== job.id) {
        client.lastCompletedId = job.id;
        showToast(job.error || t("searchFailed"), "error");
      }
      client.firstStateSeen = true;
    } catch (error) {
      if (client.online) showToast(t("disconnected"), "error");
      client.online = false;
    } finally {
      client.polling = false;
    }
  }

  function formPayload() {
    nodes.queryError.hidden = true;
    const query = nodes.query.value.trim();
    const from = Number(nodes.from.value);
    const to = Number(nodes.to.value);
    const disciplines = [...nodes.disciplines.querySelectorAll("input:checked")].map((node) => node.value);
    const sources = [...nodes.sources.querySelectorAll("input:checked")].map((node) => node.value);
    const invalid = !query ? t("needQuery") : !Number.isInteger(from) || !Number.isInteger(to) || from > to ? t("invalidYears") :
      !disciplines.length ? t("needDiscipline") : !sources.length ? t("needSource") : nodes.translate.checked && (client.config.llm_backend || "rules") === "rules" ? t("noTranslateRules") : "";
    if (invalid) {
      nodes.queryError.textContent = invalid;
      nodes.queryError.hidden = false;
      throw new Error(invalid);
    }
    return { query, years: `${from}-${to}`, limit: Number(nodes.limit.value), disciplines, sources, translate: nodes.translate.checked };
  }

  async function previewPlan() {
    const payload = formPayload();
    const data = await api("/api/plan", "POST", payload);
    client.plan = null;
    client.planInputSignature = JSON.stringify(payload);
    nodes.planPanel.hidden = true;
    client.lastJobSignature = "";
    renderJob(data.job);
  }

  async function startSearch() {
    const payload = formPayload();
    if (!client.plan || client.planInputSignature !== JSON.stringify(payload)) {
      await previewPlan();
      return;
    }
    payload.plan = editedPlan();
    const data = await api("/api/search", "POST", payload);
    client.feedback.clear();
    client.rows = [];
    nodes.planPanel.hidden = true;
    client.lastJobSignature = "";
    renderJob(data.job);
    renderResults();
  }

  function bindEvents() {
    nodes.lang.addEventListener("click", () => {
      client.lang = client.lang === "zh" ? "en" : "zh";
      localStorage.setItem("radar-language", client.lang);
      translateDom();
    });
    nodes.planButton.addEventListener("click", async () => { try { await previewPlan(); } catch (error) { showToast(error.message, "error"); } });
    nodes.searchForm.addEventListener("submit", async (event) => { event.preventDefault(); try { await startSearch(); } catch (error) { showToast(error.message, "error"); } });
    nodes.planSearchButton.addEventListener("click", async () => { try { await startSearch(); } catch (error) { showToast(error.message, "error"); } });
    nodes.stop.addEventListener("click", async () => { try { const data = await api("/api/stop", "POST", {}); renderJob(data.job); } catch (error) { showToast(error.message, "error"); } });
    nodes.deep.addEventListener("click", async () => {
      try {
        if (![...client.feedback.values()].some((v) => v !== "uncertain")) throw new Error(t("needFeedback"));
        const data = await api("/api/deep-search", "POST", { feedback: feedbackPayload() });
        client.lastJobSignature = "";
        renderJob(data.job);
      } catch (error) { showToast(error.message, "error"); }
    });
    nodes.settingsButton.addEventListener("click", () => { nodes.settingsError.hidden = true; renderConfig(); nodes.settingsDialog.showModal(); });
    [nodes.settingsClose, nodes.settingsCancel].forEach((button) => button.addEventListener("click", () => nodes.settingsDialog.close()));
    nodes.settingsForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      nodes.settingsError.hidden = true;
      try {
        const data = await api("/api/config", "POST", {
          llm_backend: selectedBackend(), provider: nodes.provider.value || "openai",
          api_key: nodes.apiKey.value.trim(), api_endpoint: nodes.apiEndpoint.value.trim(),
          api_models: nodes.apiModels.value.trim()
        });
        client.config = data.config || {};
        nodes.apiKey.value = "";
        client.notifyDesktop = nodes.desktopNotify.checked;
        localStorage.setItem("radar-desktop-notify", client.notifyDesktop ? "yes" : "no");
        if (client.notifyDesktop && "Notification" in window && Notification.permission === "default") {
          const permission = await Notification.requestPermission();
          if (permission !== "granted") showToast(t("notificationDenied"));
        }
        renderConfig();
        nodes.settingsDialog.close();
        showToast(t("settingsSaved"));
      } catch (error) {
        nodes.settingsError.textContent = error.message;
        nodes.settingsError.hidden = false;
      }
    });
    document.querySelectorAll('input[name="llm-backend"]').forEach((radio) => radio.addEventListener("change", updateBackendFields));
    nodes.provider.addEventListener("change", () => {
      const preset = (client.meta.providers || []).find((item) => item.id === nodes.provider.value);
      nodes.apiEndpoint.value = preset?.endpoint || "";
      nodes.apiModels.value = preset?.models || "";
      nodes.keyHelp.textContent = t("keyLocal");
    });
    nodes.exitButton.addEventListener("click", async () => {
      try {
        await api("/api/shutdown", "POST", {});
        nodes.settingsDialog.close();
        document.querySelector(".workspace").replaceChildren(textElement("p", "empty-state", t("appClosed")));
      } catch (error) { showToast(error.message, "error"); }
    });
    nodes.toastClose.addEventListener("click", () => { nodes.toast.hidden = true; });
  }

  async function init() {
    nodes.to.value = String(new Date().getFullYear());
    bindEvents();
    translateDom();
    try {
      client.meta = await api("/api/meta");
      renderMeta();
      await syncState();
    } catch (error) { showToast(t("optionsFailed"), "error"); }
    setInterval(syncState, 1200);
  }

  init();
})();
