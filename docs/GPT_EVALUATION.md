# GPT 评测脚本

仓库根目录的 `evaluate_gpt.py` 可用一把 OpenAI API key 跑完 General Protein QA、EC、CATH 和 Functional De Novo Design 四条轨道。脚本只依赖 Python 标准库。

## 使用

打开 `evaluate_gpt.py`，只修改顶部这一行：

```python
OPENAI_API_KEY = "PASTE_YOUR_OPENAI_API_KEY_HERE"
```

先跑 12 条 smoke test（每条轨道 3 条）：

```bash
python3 evaluate_gpt.py --smoke
```

再跑完整评测。脚本会先显示样本数和最大 API 请求数，输入 `RUN` 后才会产生费用：

```bash
python3 evaluate_gpt.py
```

中断后若希望续跑，应复用同一输出目录：

```bash
python3 evaluate_gpt.py --run-dir runs/gpt-5.6-sol-YYYYMMDD-HHMMSS
```

其他常用命令：

```bash
# 每条轨道前 20 条
python3 evaluate_gpt.py --limit 20

# 只跑 EC 和 CATH
python3 evaluate_gpt.py --tracks ec cath

# 更换待测模型或并发数，不需要修改脚本
python3 evaluate_gpt.py --model gpt-5.6-terra --concurrency 2
```

## 与论文一致的部分

- 模型输入直接使用 release JSONL 中的公开任务模板。
- 请求不提供 web search、file search、数据库或其他工具，评估模型的原生蛋白能力。
- 对 frontier LLM 保留 API 默认 temperature，省略 top-p，并设置最大输出 8192 tokens。
- 设计任务要求只返回一条由 20 种标准氨基酸组成、长度不超过 1024 的大写序列。
- EC/CATH 从完整四级编号计算 Level 1–4 累积精确准确率。
- 设计任务按论文公式计算 Rep2、Rep5，并报告有效性、格式服从率和唯一性。

## 无法只靠 OpenAI key 精确复现的部分

1. 原文 General QA 使用 Gemini 3 Flash 做语义等价 judge，但完整 rubric 没有公开。本脚本用 `gpt-5.6-luna` 和固定结构化 rubric 作为可运行代理，因此 QA 分数不能与论文榜单直接等同。
2. 原文设计评测还包含 Repeat（串联重复区域）、ESMFold-v1 pLDDT、InterProScan-5.75-106.0 功能恢复、MMseqs2 序列 novelty 和 Foldseek 结构 novelty/diversity。这些需要模型权重、冻结数据库和重型本地工具，脚本不会伪造它们；未计算项会写入 `summary.json`。
3. 当前公开 release 的 manifest 状态是 `provisional`，尚未完成对冻结历史库的 `<30%` 同源性过滤，因此结果是工程调试分数，不是正式 ProteinArena 主榜分数。

## 输出

每次运行写入独立目录：

- `predictions.jsonl`：逐样本原始回答、解析结果、格式状态、延迟、token usage 和 API response ID；
- `qa_judgments.jsonl`：QA 逐样本 judge 结论与理由；
- `summary.json`：四条轨道的汇总分数、错误、拒答和总 token 用量；
- `design_sequences.fasta`：可继续送入 ESMFold、InterProScan、MMseqs2 和 Foldseek 的有效设计序列。

API 请求设置 `store=false`。真实 key 不会写入结果，但请勿把填入 key 的脚本提交到 GitHub。
