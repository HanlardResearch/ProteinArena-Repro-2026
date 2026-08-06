const TRACK_LABELS = {
  general_qa: "General Protein QA",
  ec: "EC Prediction",
  cath: "CATH Prediction",
  design: "Functional De Novo Design"
};

const state = { data: null, track: "general_qa", currentId: null };
const summaryEl = document.querySelector("#audit-summary");
const detailEl = document.querySelector("#audit-detail");
const listEl = document.querySelector("#audit-list");
const selectEl = document.querySelector("#audit-sample");

function pretty(value) { return JSON.stringify(value, null, 2); }

function tag(text, className = "") {
  const span = document.createElement("span");
  span.className = `audit-tag ${className}`.trim(); span.textContent = text; return span;
}

function renderSummary() {
  const { summary, source } = state.data;
  const cards = Object.entries(summary.by_track).map(([track, result]) => {
    const article = document.createElement("article");
    article.append(tag(TRACK_LABELS[track]));
    const strong = document.createElement("strong"); strong.textContent = `${result.consistent}/${result.sampled}`;
    const p = document.createElement("p"); p.textContent = "机器一致性检查通过";
    article.append(strong, p); return article;
  });
  const sourceCard = document.createElement("article"); sourceCard.className = "source-card";
  sourceCard.innerHTML = `<span>RAW SOURCE</span><strong>${summary.consistent}/${summary.sampled}</strong><p>${source.database} · ${source.release_status}</p><code>SHA-256 ${source.raw_sha256}</code>`;
  summaryEl.replaceChildren(sourceCard, ...cards);
}

function currentItems() { return state.data.items.filter(item => item.track === state.track); }

function configureSelect() {
  const items = currentItems();
  selectEl.replaceChildren(...items.map(item => {
    const option = new Option(`${item.audit_id.slice(-2)} · ${item.accession}${item.constructed_sample.category ? ` · ${item.constructed_sample.category.replaceAll("_", " ")}` : ""}`, item.audit_id);
    return option;
  }));
  if (!items.some(item => item.audit_id === state.currentId)) state.currentId = items[0].audit_id;
  selectEl.value = state.currentId;
}

function codePanel(title, subtitle, value, raw = false) {
  const section = document.createElement("section"); section.className = `compare-panel${raw ? " raw-panel" : ""}`;
  const header = document.createElement("header");
  const heading = document.createElement("div");
  const h2 = document.createElement("h2"); h2.textContent = title;
  const p = document.createElement("p"); p.textContent = subtitle;
  heading.append(h2, p); header.append(heading);
  const copy = document.createElement("button"); copy.className = "copy-button"; copy.textContent = "复制 JSON";
  copy.addEventListener("click", async () => { await navigator.clipboard.writeText(pretty(value)); copy.textContent = "已复制"; setTimeout(() => copy.textContent = "复制 JSON", 1200); });
  header.append(copy);
  const pre = document.createElement("pre"); const code = document.createElement("code"); code.textContent = pretty(value); pre.append(code);
  section.append(header, pre); return section;
}

function renderDetail() {
  const item = state.data.items.find(row => row.audit_id === state.currentId);
  if (!item) return;
  const status = document.createElement("div"); status.className = "audit-status";
  const heading = document.createElement("div");
  const title = document.createElement("h2"); title.textContent = `${item.track_label} · ${item.accession}`;
  const sourceLink = document.createElement("a"); sourceLink.href = `https://rest.uniprot.org/uniprotkb/${item.accession}.json`; sourceLink.target = "_blank"; sourceLink.rel = "noreferrer"; sourceLink.textContent = "打开 UniProt 原始 API ↗";
  heading.append(title, sourceLink);
  const outcome = tag(item.consistent ? "一致性检查通过" : "存在不一致", item.consistent ? "pass" : "fail");
  status.append(heading, outcome);

  const checks = document.createElement("div"); checks.className = "check-grid";
  Object.entries(item.checks).forEach(([name, passed]) => {
    const row = document.createElement("div"); row.className = passed ? "check-pass" : "check-fail";
    row.innerHTML = `<span>${passed ? "✓" : "×"}</span><code>${name}</code>`; checks.append(row);
  });
  const paths = document.createElement("div"); paths.className = "source-paths";
  const label = document.createElement("strong"); label.textContent = "本样例使用的原始字段"; paths.append(label, ...item.source_paths.map(path => tag(path, "path")));

  const comparison = document.createElement("div"); comparison.className = "comparison-grid";
  comparison.append(
    codePanel("构建后的测评样例", "release JSONL 中实际提供给评测脚本的数据", item.constructed_sample),
    codePanel("真实源数据", "仓库 raw JSONL 中同 accession 的完整、未经改写的 UniProt JSON", item.raw_source_record, true)
  );
  detailEl.replaceChildren(status, checks, paths, comparison);
}

function renderList() {
  const buttons = currentItems().map(item => {
    const button = document.createElement("button"); button.className = `audit-list-item${item.audit_id === state.currentId ? " active" : ""}`;
    const category = item.constructed_sample.category?.replaceAll("_", " ") || item.track_label;
    button.innerHTML = `<span>${item.audit_id.slice(-2)}</span><strong>${item.accession}</strong><small>${category}</small><em>${item.consistent ? "✓" : "×"}</em>`;
    button.addEventListener("click", () => { state.currentId = item.audit_id; selectEl.value = item.audit_id; renderDetail(); renderList(); detailEl.scrollIntoView({ behavior: "smooth", block: "start" }); });
    return button;
  });
  listEl.replaceChildren(...buttons);
}

function renderTrack() { configureSelect(); renderDetail(); renderList(); }

document.querySelectorAll(".track-tab").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".track-tab").forEach(item => { item.classList.remove("active"); item.setAttribute("aria-selected", "false"); });
  button.classList.add("active"); button.setAttribute("aria-selected", "true");
  state.track = button.dataset.track; state.currentId = null; renderTrack();
}));

selectEl.addEventListener("change", () => { state.currentId = selectEl.value; renderDetail(); renderList(); });

fetch("data/audit/source_pair_audit.json")
  .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
  .then(data => { state.data = data; renderSummary(); renderTrack(); })
  .catch(error => { summaryEl.innerHTML = `<p>审计数据载入失败：${error.message}</p>`; });
