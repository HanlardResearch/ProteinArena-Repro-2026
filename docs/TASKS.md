# 任务、目标与模型模板

General Protein QA 沿用论文 5 个维度、16 类：

| 维度 | 类别 |
|---|---|
| Function | enzyme_classification, functional_domains, molecular_function, protein_family, superfamily |
| Interaction and Binding | metal_binding, nucleic_acid_binding, oligomerization, small_molecule_binding |
| Location and Modification | cleavage_sites, post_translational_modifications, primary_localization, targeting_signals |
| Physicochemical Property | hydrophobicity |
| Structure | structural_composition, transmembrane_type |

每个精确子任务维护20个语义等价的英文问法；构建时按 `random_seed + sample_id` 确定性选择一个，并在样本中记录 `template_index` 和 `template_count`。QA共16类，因此共有320个QA模板。

每条 release 样本还包含英文 `rationale`。它是面向训练/审计的短篇模型式推理：根据输入序列的长度、组成和可解释的序列模式，结合由 evidence 归一化得到的 gold answer 组织出自洽的生化推导。`rationale` 不会加入模型测评 prompt，也不直接提及 UniProt 字段名、数据库 ID 或“某字段等于某值”的外部查表过程；它不是原始 Swiss-Prot 注释，而是由构建器确定性生成的辅助文本。

通用输入模板：

```text
{paraphrased_question}
The protein is {SEQUENCE}
```

输出为简短自然语言答案。标签与 `evidence` 来自同一条 Swiss-Prot 记录。为避免把缺失注释误当阴性，本复现默认只构造有明确正证据的样本。

EC 模板（20个等价问法）：

```text
Determine the most appropriate four-level EC number for the protein whose amino-acid sequence is provided. The protein is {SEQUENCE}
```

输出严格为 `x.x.x.x`。若一条蛋白有多个 EC，分别生成带唯一 sample_id 的样本并在 manifest 统计多标签来源。

CATH 模板（20个等价问法）：

```text
Determine the most probable CATH hierarchical classification (x.x.x.x) for the provided protein sequence. The protein is {SEQUENCE}
```

输出严格为 `x.x.x.x`。本实现优先读取 UniProt 的 Gene3D 四段式交叉引用；可额外接入冻结 CATH 映射表。Gene3D 与 CATH 官方 domain assignment 并不完全等价，因此单列为偏差。

Functional De Novo Design 模板（20个等价问法）：

```text
Generate a protein sequence for a novel protein that integrates the following function keywords: {INTERPRO_NAMES}. The designed protein sequence is
```

自回归模型应只返回一条大写标准氨基酸序列，长度不超过 1024。论文对 AMix-2 AR 使用 `temperature=0.7, top_p=0.6`；理解任务为 `temperature=0.7, top_p=0.5, max_tokens=4096`。其他模型应同时报告实际采样参数。

Design 的模型输入只有上述 InterPro 功能条件，不包含任何天然氨基酸序列。数据记录中的
`reference_sequence` 和 `reference_sequence_length` 来自同一条 Swiss-Prot 来源记录，仅用于
来源审计和自然序列基线，`reference_usage` 固定为 `audit_only_not_model_input`。它们不得拼接进
模型 prompt，也不得作为序列编辑或续写的起点。

设计评测复现：Rep2/Rep5、序列有效性、唯一性；完整复现还需 ESMFold-v1 pLDDT、InterProScan 5.75-106.0 功能恢复率、MMseqs2 对历史 UniProt 的 novelty。
