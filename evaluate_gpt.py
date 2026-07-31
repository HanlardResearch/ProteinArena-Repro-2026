#!/usr/bin/env python3
"""Evaluate an OpenAI GPT model on ProteinArena-Repro-2026.

Edit only OPENAI_API_KEY below, then run:
    python3 evaluate_gpt.py --smoke
    python3 evaluate_gpt.py

The implementation intentionally uses only Python's standard library.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import random
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# ONLY EDIT THIS VALUE.
# Never commit a real key to GitHub.
# ---------------------------------------------------------------------------
OPENAI_API_KEY = "PASTE_YOUR_OPENAI_API_KEY_HERE"


# Paper-faithful defaults for frontier LLMs: default temperature, omitted top_p,
# and 8192 output tokens. The current OpenAI flagship model is explicit so each
# run records a stable model tier rather than a moving family alias.
MODEL = "gpt-5.6-sol"
JUDGE_MODEL = "gpt-5.6-luna"
API_URL = "https://api.openai.com/v1/responses"
MAX_OUTPUT_TOKENS = 8192
DEFAULT_TRACKS = ("general_qa", "ec", "cath", "design")
AA20 = frozenset("ACDEFGHIKLMNPQRSTVWY")
CODE_RE = re.compile(r"(?<![\d.])(\d+)\.(\d+)\.(\d+)\.(\d+)(?![\d.])")
AA_RUN_RE = re.compile(r"[ACDEFGHIKLMNPQRSTVWY]+")
PLACEHOLDER_KEYS = {"", "PASTE_YOUR_OPENAI_API_KEY_HERE", "sk-..."}


TRACK_INSTRUCTIONS = {
    "general_qa": (
        "Answer the protein question directly and concisely using only the provided "
        "sequence and your internal knowledge. Return only the answer: no analysis, "
        "citations, database lookup, retrieval, or tool use."
    ),
    "ec": (
        "Predict the complete four-level EC number. Return exactly one numeric code "
        "in x.x.x.x form and nothing else. Do not use retrieval or tools."
    ),
    "cath": (
        "Predict the complete four-level CATH classification. Return exactly one "
        "numeric code in x.x.x.x form and nothing else. Do not use retrieval or tools."
    ),
    "design": (
        "Design the requested protein. Return exactly one uppercase sequence made only "
        "of the 20 standard amino-acid letters ACDEFGHIKLMNPQRSTVWY, with length at "
        "most 1024 residues. Return no prose, label, spaces, or Markdown."
    ),
}


JUDGE_FORMAT = {
    "type": "json_schema",
    "name": "protein_qa_judgment",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "correct": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["correct", "reason"],
        "additionalProperties": False,
    },
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "model"


def mean(values: Iterable[float]) -> float | None:
    items = list(values)
    return statistics.fmean(items) if items else None


def rep_n(sequence: str, n: int) -> float:
    grams = [sequence[i : i + n] for i in range(max(0, len(sequence) - n + 1))]
    return 0.0 if not grams else 1.0 - len(set(grams)) / len(grams)


def extract_response_text(response: dict[str, Any]) -> tuple[str, str | None]:
    """Return assistant text and an optional refusal string from a Responses payload."""
    if isinstance(response.get("output_text"), str):
        return response["output_text"], None
    texts: list[str] = []
    refusals: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if not isinstance(part, dict):
                continue
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
            elif part.get("type") == "refusal" and isinstance(part.get("refusal"), str):
                refusals.append(part["refusal"])
    return "\n".join(texts), "\n".join(refusals) or None


def parse_hierarchical_code(text: str) -> str | None:
    match = CODE_RE.search(text)
    return ".".join(match.groups()) if match else None


def extract_protein_sequence(text: str) -> tuple[str, bool]:
    """Extract a sequence while separately tracking strict output compliance."""
    stripped = text.strip()
    strict = bool(stripped) and len(stripped) <= 1024 and set(stripped) <= AA20
    if strict:
        return stripped, True
    candidates = [run for run in AA_RUN_RE.findall(stripped) if len(run) >= 10]
    return (max(candidates, key=len), False) if candidates else ("", False)


def hierarchy_correctness(prediction: str | None, label: str) -> dict[str, bool]:
    pred = prediction.split(".") if prediction else []
    gold = label.split(".")
    return {
        f"level_{level}_correct": len(pred) == 4 and pred[:level] == gold[:level]
        for level in range(1, 5)
    }


class OpenAIResponsesClient:
    def __init__(self, api_key: str, timeout: int = 240, max_retries: int = 6):
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            API_URL,
            data=encoded,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ProteinArena-Repro-2026/0.1",
            },
        )
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:2000]
                retryable = exc.code in {408, 409, 429, 500, 502, 503, 504}
                if not retryable or attempt >= self.max_retries:
                    raise RuntimeError(f"OpenAI HTTP {exc.code}: {body}") from exc
                delay = min(60.0, (2**attempt) + random.random())
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt >= self.max_retries:
                    raise RuntimeError(f"OpenAI network error: {exc}") from exc
                delay = min(60.0, (2**attempt) + random.random())
            time.sleep(delay)
        raise AssertionError("unreachable")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_completed(path: Path, key: str = "sample_id") -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    completed: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path):
        if row.get("status") == "ok" and row.get(key):
            completed[str(row[key])] = row
    return completed


def append_jsonl(path: Path, row: dict[str, Any], lock: threading.Lock) -> None:
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    with lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()


def response_meta(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "response_id": response.get("id"),
        "response_model": response.get("model"),
        "response_status": response.get("status"),
        "incomplete_details": response.get("incomplete_details"),
        "usage": response.get("usage"),
    }


def prediction_payload(sample: dict[str, Any], model: str) -> dict[str, Any]:
    return {
        "model": model,
        "instructions": TRACK_INSTRUCTIONS[sample["track"]],
        "input": sample["prompt"],
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "store": False,
    }


def predict_one(
    client: OpenAIResponsesClient, sample: dict[str, Any], model: str
) -> dict[str, Any]:
    started = time.monotonic()
    base = {
        "sample_id": sample["sample_id"],
        "track": sample["track"],
        "category": sample.get("category"),
        "dimension": sample.get("dimension"),
        "gold": sample.get("answer", sample.get("label")),
        "requested_model": model,
        "created_at": utc_now(),
    }
    try:
        response = client.create(prediction_payload(sample, model))
        text, refusal = extract_response_text(response)
        row = {
            **base,
            "status": "ok" if text and not refusal else "refusal" if refusal else "empty",
            "raw_prediction": text,
            "refusal": refusal,
            "latency_seconds": round(time.monotonic() - started, 3),
            **response_meta(response),
        }
        if sample["track"] in {"ec", "cath"}:
            parsed = parse_hierarchical_code(text)
            row["parsed_prediction"] = parsed
            row["strict_format"] = text.strip() == parsed if parsed else False
            row.update(hierarchy_correctness(parsed, sample["label"]))
        elif sample["track"] == "design":
            sequence, strict = extract_protein_sequence(text)
            row.update(
                {
                    "parsed_sequence": sequence,
                    "strict_format": strict,
                    "sequence_valid": bool(sequence)
                    and len(sequence) <= 1024
                    and set(sequence) <= AA20,
                    "sequence_length": len(sequence) if sequence else 0,
                }
            )
        return row
    except Exception as exc:  # preserve failures for inspection and retry on next run
        return {
            **base,
            "status": "error",
            "error": str(exc),
            "latency_seconds": round(time.monotonic() - started, 3),
        }


def judge_payload(sample: dict[str, Any], prediction: dict[str, Any], model: str) -> dict[str, Any]:
    judge_input = {
        "question": sample["question"],
        "reference_answer": sample["answer"],
        "candidate_answer": prediction.get("raw_prediction", ""),
    }
    return {
        "model": model,
        "instructions": (
            "You are a strict evaluator for protein question answering. Decide whether "
            "the candidate answer is semantically equivalent to the reference answer for "
            "the question. Accept paraphrases and harmless extra specificity. Reject missing "
            "essential facts, contradictions, hedging among incompatible answers, or merely "
            "related facts. Evaluate only the supplied text. Return JSON matching the schema."
        ),
        "input": json.dumps(judge_input, ensure_ascii=False),
        "max_output_tokens": 1024,
        "store": False,
        "text": {"format": JUDGE_FORMAT},
    }


def judge_one(
    client: OpenAIResponsesClient,
    sample: dict[str, Any],
    prediction: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    started = time.monotonic()
    base = {
        "sample_id": sample["sample_id"],
        "track": "general_qa",
        "category": sample.get("category"),
        "dimension": sample.get("dimension"),
        "judge_model": model,
        "created_at": utc_now(),
    }
    if prediction.get("status") != "ok":
        return {
            **base,
            "status": "ok",
            "correct": False,
            "reason": f"Prediction status was {prediction.get('status')}",
            "latency_seconds": 0.0,
        }
    try:
        response = client.create(judge_payload(sample, prediction, model))
        text, refusal = extract_response_text(response)
        if refusal:
            raise RuntimeError(f"Judge refusal: {refusal}")
        judgment = json.loads(text)
        if not isinstance(judgment.get("correct"), bool):
            raise ValueError("Judge response lacks boolean 'correct'")
        return {
            **base,
            "status": "ok",
            "correct": judgment["correct"],
            "reason": str(judgment.get("reason", "")),
            "latency_seconds": round(time.monotonic() - started, 3),
            **response_meta(response),
        }
    except Exception as exc:
        return {
            **base,
            "status": "error",
            "error": str(exc),
            "latency_seconds": round(time.monotonic() - started, 3),
        }


def grouped_accuracy(rows: list[dict[str, Any]], field: str, group: str) -> dict[str, Any]:
    buckets: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        if row.get(group) is not None and isinstance(row.get(field), bool):
            buckets[str(row[group])].append(row[field])
    return {
        key: {"count": len(values), "accuracy": sum(values) / len(values)}
        for key, values in sorted(buckets.items())
    }


def summarize(
    predictions: list[dict[str, Any]], judgments: list[dict[str, Any]]
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "created_at": utc_now(),
        "counts": {},
        "metrics": {},
        "usage": {},
        "paper_metrics_not_computed": [
            "Design Repeat (tandem-region metric from Kuang et al.)",
            "ESMFold-v1 mean pLDDT",
            "InterProScan-5.75-106.0 function recovery",
            "MMseqs2 sequence novelty against UniProt through 2025-12-31",
            "Foldseek structure novelty/diversity",
        ],
    }
    for track in DEFAULT_TRACKS:
        rows = [row for row in predictions if row.get("track") == track]
        result["counts"][track] = {
            "attempted": len(rows),
            "ok": sum(row.get("status") == "ok" for row in rows),
            "errors": sum(row.get("status") == "error" for row in rows),
            "refusals": sum(row.get("status") == "refusal" for row in rows),
        }

    valid_judgments = [row for row in judgments if row.get("status") == "ok"]
    result["metrics"]["general_qa"] = {
        "attempted": len(judgments),
        "scored": len(valid_judgments),
        "judge_errors": sum(row.get("status") == "error" for row in judgments),
        "accuracy": (
            sum(bool(row.get("correct")) for row in valid_judgments) / len(judgments)
            if judgments
            else None
        ),
        "accuracy_scored_only": mean(float(row["correct"]) for row in valid_judgments),
        "by_category": grouped_accuracy(valid_judgments, "correct", "category"),
        "by_dimension": grouped_accuracy(valid_judgments, "correct", "dimension"),
        "judge_note": (
            "OpenAI GPT judge proxy; the paper used Gemini 3 Flash and did not release "
            "its complete rubric, so this score is not directly leaderboard-comparable. "
            "The primary accuracy treats judge errors as incorrect (fail closed)."
        ),
    }

    for track in ("ec", "cath"):
        rows = [row for row in predictions if row.get("track") == track]
        result["metrics"][track] = {
            "count": len(rows),
            "strict_format_fraction": mean(float(bool(row.get("strict_format"))) for row in rows),
            **{
                f"level_{level}_accuracy": mean(
                    float(bool(row.get(f"level_{level}_correct"))) for row in rows
                )
                for level in range(1, 5)
            },
        }

    design_rows = [row for row in predictions if row.get("track") == "design"]
    valid_sequences = [
        row["parsed_sequence"] for row in design_rows if row.get("sequence_valid")
    ]
    result["metrics"]["design"] = {
        "count": len(design_rows),
        "strict_format_fraction": mean(
            float(bool(row.get("strict_format"))) for row in design_rows
        ),
        "valid_sequence_fraction": mean(
            float(bool(row.get("sequence_valid"))) for row in design_rows
        ),
        "mean_length": mean(float(len(seq)) for seq in valid_sequences),
        "rep2_mean": mean(rep_n(seq, 2) for seq in valid_sequences),
        "rep5_mean": mean(rep_n(seq, 5) for seq in valid_sequences),
        "unique_fraction": (
            len(set(valid_sequences)) / len(valid_sequences) if valid_sequences else None
        ),
    }

    usage_rows = predictions + judgments
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        result["usage"][key] = sum(
            int(row.get("usage", {}).get(key, 0) or 0)
            for row in usage_rows
            if isinstance(row.get("usage"), dict)
        )
    result["usage"]["api_responses"] = sum(
        bool(row.get("response_id")) for row in usage_rows
    )
    return result


def export_design_fasta(predictions: list[dict[str, Any]], path: Path) -> None:
    lines: list[str] = []
    for row in predictions:
        if row.get("track") == "design" and row.get("sequence_valid"):
            lines.extend([f">{row['sample_id']}", row["parsed_sequence"]])
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def selected_samples(dataset_dir: Path, tracks: tuple[str, ...], limit: int | None) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for track in tracks:
        path = dataset_dir / f"{track}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"Missing dataset file: {path}")
        rows = load_jsonl(path)
        samples.extend(rows[:limit] if limit is not None else rows)
    return samples


def validate_key() -> str:
    key = OPENAI_API_KEY.strip()
    if key in PLACEHOLDER_KEYS:
        raise SystemExit(
            "请先打开 evaluate_gpt.py，只把 OPENAI_API_KEY 顶部占位符替换为你的 key。"
        )
    return key


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate GPT on ProteinArena-Repro-2026 using the Responses API."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parent / "data/releases/repro_2026",
    )
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--tracks", nargs="+", choices=DEFAULT_TRACKS, default=list(DEFAULT_TRACKS))
    parser.add_argument("--limit", type=int, help="Maximum samples per selected track")
    parser.add_argument("--smoke", action="store_true", help="Run 3 samples per selected track")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--no-judge", action="store_true", help="Skip General QA semantic judging")
    parser.add_argument("--yes", action="store_true", help="Skip the full-run confirmation")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.concurrency < 1:
        parser.error("--concurrency must be positive")
    if args.smoke:
        args.limit = 3
        args.yes = True
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    api_key = validate_key()
    tracks = tuple(args.tracks)
    samples = selected_samples(args.dataset.resolve(), tracks, args.limit)
    manifest_path = args.dataset / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = (args.run_dir or Path(__file__).resolve().parent / "runs" / f"{safe_slug(args.model)}-{stamp}").resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = run_dir / "predictions.jsonl"
    judgments_path = run_dir / "qa_judgments.jsonl"

    qa_count = sum(sample["track"] == "general_qa" for sample in samples)
    expected_calls = len(samples) + (0 if args.no_judge else qa_count)
    print(f"Dataset: {args.dataset.resolve()}")
    print(f"Dataset status: {manifest.get('status', 'unknown')}")
    print(f"Model: {args.model}; QA judge: {'disabled' if args.no_judge else args.judge_model}")
    print(f"Samples: {len(samples)}; maximum API calls: {expected_calls}")
    print(f"Output: {run_dir}")
    if manifest.get("status") != "official_candidate":
        print("WARNING: this dataset release is provisional and not a formal leaderboard split.")
    if not args.yes:
        answer = input("This may incur substantial API cost. Type RUN to continue: ").strip()
        if answer != "RUN":
            print("Cancelled.")
            return 1

    client = OpenAIResponsesClient(api_key)
    write_lock = threading.Lock()
    completed_predictions = load_completed(predictions_path)
    pending = [sample for sample in samples if sample["sample_id"] not in completed_predictions]
    print(f"Generating {len(pending)} predictions ({len(completed_predictions)} resumed)...")

    done_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(predict_one, client, sample, args.model): sample for sample in pending}
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            append_jsonl(predictions_path, row, write_lock)
            done_count += 1
            if done_count == 1 or done_count % 25 == 0 or done_count == len(pending):
                print(f"  predictions {done_count}/{len(pending)}; latest={row['status']}")

    all_prediction_rows = load_jsonl(predictions_path) if predictions_path.exists() else []
    latest_predictions: dict[str, dict[str, Any]] = {}
    for row in all_prediction_rows:
        sample_id = row["sample_id"]
        if sample_id not in latest_predictions or row.get("status") == "ok":
            latest_predictions[sample_id] = row
    selected_predictions = [latest_predictions[sample["sample_id"]] for sample in samples]

    judgments: list[dict[str, Any]] = []
    if not args.no_judge and "general_qa" in tracks:
        qa_samples = [sample for sample in samples if sample["track"] == "general_qa"]
        completed_judgments = load_completed(judgments_path)
        pending_qa = [sample for sample in qa_samples if sample["sample_id"] not in completed_judgments]
        print(f"Judging {len(pending_qa)} QA answers ({len(completed_judgments)} resumed)...")
        done_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {
                pool.submit(
                    judge_one,
                    client,
                    sample,
                    latest_predictions[sample["sample_id"]],
                    args.judge_model,
                ): sample
                for sample in pending_qa
            }
            for future in concurrent.futures.as_completed(futures):
                row = future.result()
                append_jsonl(judgments_path, row, write_lock)
                done_count += 1
                if done_count == 1 or done_count % 25 == 0 or done_count == len(pending_qa):
                    print(f"  judgments {done_count}/{len(pending_qa)}; latest={row['status']}")
        all_judgment_rows = load_jsonl(judgments_path) if judgments_path.exists() else []
        latest_judgments: dict[str, dict[str, Any]] = {}
        for row in all_judgment_rows:
            sample_id = row["sample_id"]
            if sample_id not in latest_judgments or row.get("status") == "ok":
                latest_judgments[sample_id] = row
        judgments = [latest_judgments[sample["sample_id"]] for sample in qa_samples]

    summary = summarize(selected_predictions, judgments)
    summary.update(
        {
            "benchmark": "ProteinArena-Repro-2026",
            "dataset_dir": str(args.dataset.resolve()),
            "dataset_status": manifest.get("status", "unknown"),
            "requested_model": args.model,
            "judge_model": None if args.no_judge else args.judge_model,
            "sampling": {
                "temperature": "API default (omitted)",
                "top_p": "omitted",
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "reasoning": "model default (omitted)",
            },
        }
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    export_design_fasta(selected_predictions, run_dir / "design_sequences.fasta")
    print("\nRESULTS")
    print(json.dumps(summary["metrics"], ensure_ascii=False, indent=2))
    print(f"\nSaved complete results to {run_dir}")
    return 0 if all(row.get("status") != "error" for row in selected_predictions) else 2


if __name__ == "__main__":
    raise SystemExit(main())
