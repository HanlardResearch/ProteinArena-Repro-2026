# 数据源与冻结策略

## 候选和标签

- UniProtKB/Swiss-Prot REST：`reviewed:true AND date_created:[CUT TO *]`。
- 时间字段：JSON `entryAudit.firstPublicDate`，构建器再次本地校验。
- QA/EC：当前 Swiss-Prot 结构化注释与 curator comments。
- CATH：当前 UniProt Gene3D cross-reference（代理）；严格版应固定 CATH release mapping。
- Design：当前 Swiss-Prot 的 InterPro accession 与 EntryName。

下载器保存原始 JSONL、SHA-256，以及 API 响应头中的 `x-uniprot-release`、release date 和 total results。发布时不得只保存派生样本。

## 历史同源性参考库

论文称候选相对截止日前发布的“any sequence”做 sequence-identity 控制，因此正式复现应使用全 UniProtKB，而非仅 Swiss-Prot。可选策略：

1. **日期精确、注释现行：** 从 UniProt REST/stream 查询 `date_created:[* TO 2025-12-31]` 的 FASTA；覆盖日期边界，但无法恢复已删除条目或旧序列版本。
2. **release 冻结、日期近似：** 使用 UniProt previous release 的完整 knowledgebase tar，并记录 release、文件 SHA-256。2025_04 在历史目录中，但目录时间为 2026-01-26；使用前必须核对 release notes 和冻结日期，不能仅按目录名假设其严格早于截止日。
3. **最严格：** 冻结 release 后再以记录首次公开日期过滤，并用 UniSave 恢复截止日时的序列版本；成本最高，但最接近时间因果要求。

本项目不替使用者静默选择。`manifest.json` 应补录参考库文件、来源 URL、release、SHA-256 和 MMseqs2 命令。

## 原始来源

- AMix-2 / ProteinArena: https://arxiv.org/abs/2605.30963
- UniProt downloads: https://www.uniprot.org/help/downloads
- UniProt previous releases: https://ftp.uniprot.org/pub/databases/uniprot/previous_releases/
- InterProScan 5.75-106.0: https://ftp.ebi.ac.uk/pub/software/unix/iprscan/5/5.75-106.0/

