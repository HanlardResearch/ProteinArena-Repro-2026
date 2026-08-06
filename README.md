# ProteinArena-Repro-2026

ProteinArena-Repro-2026 是对 AMix-2 论文中 ProteinArena 的**科学复现工程**，不是官方数据集，也不声称重建出作者未公开的私有样本。

- 在线数据浏览器：https://hanlardresearch.github.io/ProteinArena-Repro-2026/
- 40 条源数据一致性审计：https://hanlardresearch.github.io/ProteinArena-Repro-2026/audit.html
- GitHub：https://github.com/HanlardResearch/ProteinArena-Repro-2026

它复现论文公开描述的核心协议：

- 时间感知：仅使用切分日之后首次公开的 reviewed Swiss-Prot 条目；
- 同源性控制：主榜只保留与历史库最大序列一致性 `<30%` 的条目；
- 原生能力评估：推理时禁止检索、数据库查询和工作流工具；
- 四条任务轨道：General Protein QA（16 类 / 5 个维度）、EC、CATH、Functional De Novo Design；
- 可追溯：每条样本保留 accession、首次公开日期、注释证据、构建器版本和同源性状态。

默认 `repro_2026` 是向前滚动一年的复现：测试条目首次公开日期从 2026-01-01 起，历史参考库截至 2025-12-31。`paper_2025` 配置保留论文原始切分：测试条目从 2025-01-01 起，历史参考库截至 2024-12-31。

## 快速开始

无需 Python 第三方包：

```bash
python3 -m proteinarena_repro fetch --profile configs/repro_2026.json --limit 50
python3 -m proteinarena_repro prepare-homology --profile configs/repro_2026.json
# 用 MMseqs2 将 data/interim/candidates.fasta 对历史库搜索，输出 data/interim/homology.tsv
scripts/run_mmseqs.sh data/interim/candidates.fasta /path/to/frozen_historical.fasta data/interim/homology.tsv /path/to/mmseqs_tmp
python3 -m proteinarena_repro build --profile configs/repro_2026.json \
  --homology-tsv data/interim/homology.tsv \
  --homology-complete-marker data/interim/homology.tsv.complete.json
python3 -m proteinarena_repro validate --dataset data/releases/repro_2026
python3 scripts/build_pair_audit.py
```

仅用于检查解析器的真实数据 smoke test 可以显式跳过同源性门控；其产物会被强制标记为 `provisional`，不得用于正式榜单：

```bash
python3 -m proteinarena_repro build --profile configs/repro_2026.json --allow-unfiltered
```

详见 [复现协议](docs/PROTOCOL.md)、[任务与模板](docs/TASKS.md)、[数据源](docs/DATA_SOURCES.md) 和 [与原文潜在不一致处](docs/DEVIATIONS.md)。

## 用 GPT API 评测

仓库提供一个无第三方依赖的单文件入口。只需在 `evaluate_gpt.py` 顶部填入 OpenAI API key：

```bash
# 每条轨道先跑 3 条
python3 evaluate_gpt.py --smoke

# 完整评测（产生费用前会要求确认）
python3 evaluate_gpt.py
```

脚本覆盖 General QA、EC、CATH 和 Design，支持失败重试、断点续跑，输出逐条预测、QA judge、汇总指标和设计 FASTA。详细的论文一致项与不可复现项见 [GPT 评测说明](docs/GPT_EVALUATION.md)。

## 输出

正式 release 目录包含：

- `general_qa.jsonl`：16 类自然语言问答；
- `ec.jsonl`：四级 EC 分类；
- `cath.jsonl`：四级 CATH 分类；
- `design.jsonl`：InterPro 条件的功能蛋白设计；模型输入仅为功能条件，天然序列以 `reference_sequence` 保存并明确标记为仅供审计；
- `manifest.json`：配置、输入哈希、计数、过滤状态和偏差；
- `candidates.fasta`：通过时间条件的候选序列。

原始 UniProt API 响应以 `data/raw/repro_2026_uniprot.jsonl.gz` 无损压缩公开；解压后 SHA-256 见 release manifest，API release 响应头保存在相邻 metadata JSON。

任何未通过 `<30%` 历史同源性验证的数据都不会被标成正式 release。

## 许可

构建代码采用 MIT License。派生数据采用 CC BY 4.0，并保留 UniProtKB/Swiss-Prot 来源归属；详见 `DATA_LICENSE.md`。
