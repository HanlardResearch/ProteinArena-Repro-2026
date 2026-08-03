# 与原文可能不一致之处

以下差异不应被隐藏；每次构建也会把它们写入 manifest。

1. **数据未公开。** 原文没有发布 ProteinArena 的 accession 清单、逐类配额、完整问题改写、QA 标准答案或数据清洗代码，因此无法逐条复原作者的 481/870 个样本。
2. **2026 时间窗。** 默认配置将切分滚动为 2026/2025；它复现原则而非原论文 2025/2024 的精确集合。工程同时提供 `paper_2025` 配置。
3. **首次公开日期的历史可变性。** 当前 UniProt REST 返回的是现行注释状态；严格复现应保存冻结 release 和查询响应。后续 annotation update 可能改变答案，但不改变 first public date。
4. **同源性实现细节未公开。** 原文只说明 30% sequence identity 与 MMseqs2，未披露 sensitivity、coverage、alignment mode、数据库版本和 tie handling。本项目默认 sensitivity 7.5、不另设 coverage cutoff，并用 complete marker 记录版本及输入哈希；这些仍是复现方选择。
5. **QA 抽取规则未公开。** 本项目只用可审计的结构化字段/curator 文本抽取；通常不把注释缺失当作“No”。为覆盖论文明确给出的 “no targeting signal” 答案空间，仅对“明确细胞质定位且无 Signal/Transit feature”构造保守阴性。这可能与作者的人工整理、CARE 来源和 paraphrase 流程不同。
6. **481 条的类别分布未知。** 工程采用确定性平衡配额（481 = 31 + 15×30），而论文 Figure 4 的精确原始计数没有机器可读发布。
7. **CATH 映射。** UniProt Gene3D 四段编号可用于可运行复现，但不等同于作者使用的冻结 CATH domain labels。正式版应接入指定 CATH release 的 UniProt-to-domain 映射。
8. **设计关键词选择。** 原文说明使用 expert-reviewed InterPro keywords，但未发布“关键词”的具体字段、组合与去重规则。本项目直接采用记录中 InterPro accession/name，确定性去重。
9. **语义评分器。** 原文的 General QA 依赖语义等价判断，但没有公开完整 judge rubric、版本锁定输出和全部参考答案。本项目保留结构化 gold/evidence，judge 需另行版本锁定。
10. **完整设计工具链较重。** ESMFold-v1、InterProScan-5.75-106.0 和全量 MMseqs2 数据库不随仓库分发；未运行这些工具时只输出 core metrics，不得宣称完整复现论文设计分数。
11. **自然序列不是设计输入或唯一答案。** `reference_sequence` 只用于来源审计和自然序列基线，模型输入不会泄露它；训练或 few-shot 使用时必须另做去污染审计。
