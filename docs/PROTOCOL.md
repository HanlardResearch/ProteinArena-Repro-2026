# 复现协议

## 1. 不可变原则

依据 AMix-2 §4 与附录 §9–11，ProteinArena-Repro-2026 固定以下原则：

1. 候选来源为 UniProtKB reviewed（Swiss-Prot），以 `entryAudit.firstPublicDate` 做时间切分。
2. 主测试集要求候选序列相对历史参考库的最大序列一致性严格小于 30%。
3. 30–50%、50–70%、70–100% 仅作为补充同源性分桶。
4. 正式推理只向模型提供题目和蛋白序列/功能约束，不允许外部检索、数据库查询或工具编排。
5. QA 为 16 类、5 个维度；EC 和 CATH 输出完整四级编号；设计任务由 InterPro 条件驱动。
6. 正式样本必须可以回溯到原始记录和抽取证据，且不能用模型猜测标签。

## 2. 2026 滚动切分

`repro_2026` 将论文的时间协议向前滚动一年：

- 测试候选：`firstPublicDate >= 2026-01-01`；
- 历史参考：截至 `2025-12-31` 已公开的序列；
- 主榜：对历史参考的 `max_seq_identity < 0.30`。

这保持了论文的因果顺序，但不是论文原始测试集。要重建论文日期窗口，请使用 `paper_2025`。

## 3. 数据流

```text
UniProt REST (reviewed + first-public-date)
  -> 原始 JSONL（不改写）
  -> 时间与序列合法性检查
  -> candidates.fasta
  -> MMseqs2 对冻结历史库搜索
  -> <30% 主集 / 补充分桶
  -> 证据驱动的任务抽取
  -> 去重、配额、确定性排序
  -> JSONL + manifest + validate
```

正式构建建议使用冻结的 UniProt 历史 release，而不是当前库上的日期查询来模拟历史库。MMseqs2 输出至少需要三列：`query target fident`；`fident` 可为 0–1 或百分比，解析器会归一化。

## 4. 样本资格

- 序列只能包含标准 20 种氨基酸；含 `B/J/O/U/X/Z/*` 的记录排除。
- `firstPublicDate` 必须满足配置日期。
- 正式主榜必须有 MMseqs2 命中汇总；无命中按 0 处理，但搜索过程本身必须成功并记录。
- 同一轨道按 `sample_id` 去重；QA 同一 accession 可贡献不同类别。
- 标签仅从结构化注释或明确的 curator 文本抽取。一般不把缺失注释当阴性；唯一默认阴性规则是“明确细胞质定位且无 Signal/Transit feature”可标为无 targeting signal，该规则来自论文答案空间但属于复现推断。
- EC/CATH 仅保留恰有一个完整四级标签的蛋白，避免同一输入对应多个冲突 gold label。

## 5. 发布门槛

只有同时满足以下条件的目录才是 `official_candidate`：同源性 TSV 已提供、所有保留样本 `<0.30`、manifest 包含输入 SHA-256、验证器无 error。使用 `--allow-unfiltered` 的目录一律为 `provisional`。
