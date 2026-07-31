# 任务、目标与模型模板

General Protein QA 沿用论文 5 个维度、16 类：

| 维度 | 类别 |
|---|---|
| Function | enzyme_classification, functional_domains, molecular_function, protein_family, superfamily |
| Interaction and Binding | metal_binding, nucleic_acid_binding, oligomerization, small_molecule_binding |
| Location and Modification | cleavage_sites, post_translational_modifications, primary_localization, targeting_signals |
| Physicochemical Property | hydrophobicity |
| Structure | structural_composition, transmembrane_type |

通用输入模板：

```text
{paraphrased_question}
The protein is {SEQUENCE}
```

输出为简短自然语言答案。标签与 `evidence` 来自同一条 Swiss-Prot 记录。为避免把缺失注释误当阴性，本复现默认只构造有明确正证据的样本。

EC 模板：

```text
Determine the most appropriate four-level EC number for the protein whose amino-acid sequence is provided. The protein is {SEQUENCE}
```

输出严格为 `x.x.x.x`。若一条蛋白有多个 EC，分别生成带唯一 sample_id 的样本并在 manifest 统计多标签来源。

CATH 模板：

```text
Determine the most probable CATH hierarchical classification (x.x.x.x) for the provided protein sequence. The protein is {SEQUENCE}
```

输出严格为 `x.x.x.x`。本实现优先读取 UniProt 的 Gene3D 四段式交叉引用；可额外接入冻结 CATH 映射表。Gene3D 与 CATH 官方 domain assignment 并不完全等价，因此单列为偏差。

Functional De Novo Design 模板：

```text
Generate a protein sequence for a novel protein that integrates the following function keywords: {INTERPRO_NAMES}. The designed protein sequence is
```

自回归模型应只返回一条大写标准氨基酸序列，长度不超过 1024。论文对 AMix-2 AR 使用 `temperature=0.7, top_p=0.6`；理解任务为 `temperature=0.7, top_p=0.5, max_tokens=4096`。其他模型应同时报告实际采样参数。

设计评测复现：Rep2/Rep5、序列有效性、唯一性；完整复现还需 ESMFold-v1 pLDDT、InterProScan 5.75-106.0 功能恢复率、MMseqs2 对历史 UniProt 的 novelty。

