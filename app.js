const TRACKS = {
  general_qa: { file: "general_qa.jsonl", label: "General QA" },
  ec: { file: "ec.jsonl", label: "EC Prediction" },
  cath: { file: "cath.jsonl", label: "CATH Prediction" },
  design: { file: "design.jsonl", label: "Functional Design" }
};

const state = { track: "general_qa", data: {}, filtered: [], page: 1, pageSize: 12, query: "", category: "" };
const els = {
  samples: document.querySelector("#samples"), resultCount: document.querySelector("#result-count"),
  pageLabel: document.querySelector("#page-label"), prev: document.querySelector("#prev"), next: document.querySelector("#next"),
  search: document.querySelector("#search"), category: document.querySelector("#category"), categoryLabel: document.querySelector("#category-label")
};

function parseJsonl(text) {
  return text.trim().split("\n").filter(Boolean).map(line => JSON.parse(line));
}

async function loadTrack(track) {
  if (!state.data[track]) {
    els.samples.replaceChildren(makeMessage("正在载入真实 JSONL 数据…"));
    const response = await fetch(`data/releases/repro_2026/${TRACKS[track].file}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data[track] = parseJsonl(await response.text());
  }
  configureCategories();
  applyFilters();
}

function configureCategories() {
  const isQa = state.track === "general_qa";
  els.categoryLabel.hidden = !isQa;
  els.category.replaceChildren(new Option("全部 16 类", ""));
  if (!isQa) return;
  const categories = [...new Set(state.data.general_qa.map(row => row.category))].sort();
  categories.forEach(category => els.category.add(new Option(category.replaceAll("_", " "), category)));
  els.category.value = state.category;
}

function applyFilters() {
  const q = state.query.trim().toLowerCase();
  state.filtered = state.data[state.track].filter(row => {
    if (state.track === "general_qa" && state.category && row.category !== state.category) return false;
    if (!q) return true;
    const haystack = [row.accession, row.category, row.question, row.answer, row.label, row.prompt,
      ...(row.evidence || []), ...(row.interpro || []).flatMap(x => [x.id, x.name])].filter(Boolean).join(" ").toLowerCase();
    return haystack.includes(q);
  });
  const maxPage = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  state.page = Math.min(state.page, maxPage);
  render();
}

function makeMessage(text) {
  const p = document.createElement("p"); p.className = "empty"; p.textContent = text; return p;
}

function sampleCard(row) {
  const article = document.createElement("article"); article.className = "sample";
  const top = document.createElement("div"); top.className = "sample-top";
  const badge = document.createElement("span"); badge.className = "badge";
  badge.textContent = row.category?.replaceAll("_", " ") || TRACKS[row.track].label;
  const accession = document.createElement("a"); accession.className = "accession";
  accession.href = row.source.url; accession.target = "_blank"; accession.rel = "noreferrer"; accession.textContent = row.accession + " ↗";
  top.append(badge, accession);

  const title = document.createElement("h3");
  title.textContent = row.question || (row.track === "design" ? row.prompt : `预测完整四级 ${row.track.toUpperCase()} 编号`);
  article.append(top, title);

  if (row.track !== "design") {
    const answer = document.createElement("p"); answer.className = "answer";
    answer.textContent = `Gold · ${row.answer || row.label}`; article.append(answer);
    article.append(field("Input sequence", row.sequence, "sequence"));
  } else {
    article.append(field("InterPro constraints", row.interpro.map(x => `${x.id} · ${x.name}`).join("; ")));
    article.append(field("Natural reference sequence · audit only, not provided to the model", row.reference_sequence, "sequence"));
  }
  const evidence = row.evidence?.join("; ") || (row.track === "design" ? "Swiss-Prot InterPro cross-references" : row.mapping_type || "Structured annotation");
  article.append(field("Evidence", evidence));
  const sequenceLength = row.track === "design" ? row.reference_sequence_length : row.sequence_length;
  article.append(field("Audit", `${row.first_public_date} · ${row.homology_bin} · ${sequenceLength} aa`));
  return article;
}

function field(label, value, className = "") {
  const div = document.createElement("div"); div.className = "field";
  const strong = document.createElement("strong"); strong.textContent = label;
  const p = document.createElement("p"); p.textContent = value; if (className) p.className = className;
  div.append(strong, p); return div;
}

function render() {
  const start = (state.page - 1) * state.pageSize;
  const rows = state.filtered.slice(start, start + state.pageSize);
  els.samples.replaceChildren(...(rows.length ? rows.map(sampleCard) : [makeMessage("没有匹配的任务实例。") ]));
  const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  els.resultCount.textContent = `${TRACKS[state.track].label} · ${state.filtered.length.toLocaleString()} 条结果`;
  els.pageLabel.textContent = `第 ${state.page} / ${pages} 页`;
  els.prev.disabled = state.page <= 1; els.next.disabled = state.page >= pages;
}

document.querySelectorAll(".track-tab").forEach(button => button.addEventListener("click", async () => {
  document.querySelectorAll(".track-tab").forEach(x => { x.classList.remove("active"); x.setAttribute("aria-selected", "false"); });
  button.classList.add("active"); button.setAttribute("aria-selected", "true");
  state.track = button.dataset.track; state.page = 1; state.category = "";
  try { await loadTrack(state.track); } catch (error) { els.samples.replaceChildren(makeMessage(`数据载入失败：${error.message}`)); }
}));

els.search.addEventListener("input", () => { state.query = els.search.value; state.page = 1; applyFilters(); });
els.category.addEventListener("change", () => { state.category = els.category.value; state.page = 1; applyFilters(); });
els.prev.addEventListener("click", () => { if (state.page > 1) { state.page--; render(); document.querySelector("#explorer").scrollIntoView(); } });
els.next.addEventListener("click", () => { if (state.page * state.pageSize < state.filtered.length) { state.page++; render(); document.querySelector("#explorer").scrollIntoView(); } });

fetch("data/releases/repro_2026/manifest.json").then(r => r.json()).then(manifest => {
  document.querySelector("#candidate-count").textContent = manifest.input.records.toLocaleString();
  document.querySelector("#qa-count").textContent = manifest.counts.general_qa.toLocaleString();
  document.querySelector("#ec-count").textContent = manifest.counts.ec.toLocaleString();
  document.querySelector("#cath-count").textContent = manifest.counts.cath.toLocaleString();
  document.querySelector("#design-count").textContent = manifest.counts.design.toLocaleString();
}).catch(() => {});

loadTrack("general_qa").catch(error => els.samples.replaceChildren(makeMessage(`数据载入失败：${error.message}`)));
