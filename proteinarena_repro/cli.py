from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

from .builders import build_all
from .homology import parse_mmseqs, verify_complete_marker
from .io_utils import project_path, read_json, read_jsonl, sha256, write_jsonl
from .uniprot import fetch_reviewed_since


def load_profile(path: Path) -> tuple[dict, dict[str, Path]]:
    profile = read_json(path)
    paths = {k: project_path(path, profile[k]) for k in ("raw_path", "interim_dir", "release_dir")}
    return profile, paths


def cmd_fetch(args: argparse.Namespace) -> None:
    profile, paths = load_profile(args.profile)
    result = fetch_reviewed_since(profile["test_first_public_date_from"], paths["raw_path"], args.limit, profile["uniprot_page_size"])
    print(json.dumps({"downloaded": result["count"], "path": str(paths["raw_path"]),
                      "sha256": sha256(paths["raw_path"]), "metadata_path": result["metadata_path"],
                      "uniprot": result["metadata"]}, indent=2))


def eligible(entry: dict, profile: dict) -> bool:
    return entry.get("entryType", "").startswith("UniProtKB reviewed") and entry.get("entryAudit", {}).get("firstPublicDate", "") >= profile["test_first_public_date_from"]


def cmd_prepare(args: argparse.Namespace) -> None:
    profile, paths = load_profile(args.profile)
    entries = [x for x in read_jsonl(paths["raw_path"]) if eligible(x, profile)]
    out = paths["interim_dir"] / "candidates.fasta"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(f">{entry['primaryAccession']} first_public={entry['entryAudit']['firstPublicDate']}\n{entry['sequence']['value']}\n")
    print(json.dumps({"candidates": len(entries), "fasta": str(out), "sha256": sha256(out)}, indent=2))


def cmd_build(args: argparse.Namespace) -> None:
    profile, paths = load_profile(args.profile)
    raw = paths["raw_path"]
    entries = [x for x in read_jsonl(raw) if eligible(x, profile)]
    identities = parse_mmseqs(args.homology_tsv) if args.homology_tsv else None
    homology_marker = None
    if identities is not None:
        if not args.homology_complete_marker:
            raise SystemExit("Formal builds require --homology-complete-marker from scripts/run_mmseqs.sh.")
        fasta = paths["interim_dir"] / "candidates.fasta"
        homology_marker = verify_complete_marker(args.homology_complete_marker, fasta, sha256(fasta))
    if identities is None and not args.allow_unfiltered:
        raise SystemExit("A homology TSV is required for a formal build; use --allow-unfiltered only for a provisional smoke test.")
    tracks = build_all(entries, identities, profile, args.allow_unfiltered)
    release = paths["release_dir"]
    release.mkdir(parents=True, exist_ok=True)
    counts = {track: write_jsonl(release / f"{track}.jsonl", rows) for track, rows in tracks.items()}
    deviations = [
        "Original accession list, per-category quotas, paraphrases, and extraction code were not released.",
        "repro_2026 rolls the temporal split forward one year." if profile["profile"] == "repro_2026" else "Current UniProt annotations may differ from the frozen records used by the authors.",
        "CATH labels use UniProt Gene3D cross-references as a proxy unless a frozen CATH mapping is supplied.",
        "QA extraction rules are reconstructed; only cytoplasmic records without Signal/Transit features receive a conservative negative targeting label."
    ]
    raw_meta_path = raw.with_suffix(raw.suffix + ".meta.json")
    raw_meta = read_json(raw_meta_path) if raw_meta_path.exists() else None
    manifest = {
        "name": profile["name"], "profile": profile["profile"],
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "provisional" if identities is None else "official_candidate",
        "config": profile, "input": {"raw_path": str(raw), "raw_sha256": sha256(raw), "records": len(entries),
                                       "api_metadata_path": str(raw_meta_path) if raw_meta else None,
                                       "api_metadata_sha256": sha256(raw_meta_path) if raw_meta else None,
                                       "api_metadata": raw_meta},
        "homology": {"verified": identities is not None, "tsv": str(args.homology_tsv) if args.homology_tsv else None,
                      "tsv_sha256": sha256(args.homology_tsv) if args.homology_tsv else None,
                      "complete_marker": str(args.homology_complete_marker) if args.homology_complete_marker else None,
                      "run": homology_marker,
                      "threshold_exclusive": profile["primary_max_sequence_identity_exclusive"]},
        "counts": counts, "deviations": deviations,
        "paper": "AMix-2: Establishing Protein as a Native Modality in Large Language Models, arXiv:2605.30963"
    }
    (release / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


def cmd_validate(args: argparse.Namespace) -> None:
    release = args.dataset
    manifest = read_json(release / "manifest.json")
    errors, warnings = [], []
    seen = set()
    pattern = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]+$")
    for track in ("general_qa", "ec", "cath", "design"):
        path = release / f"{track}.jsonl"
        rows = list(read_jsonl(path))
        if len(rows) != manifest["counts"][track]: errors.append(f"{track}: manifest count mismatch")
        for row in rows:
            if row["sample_id"] in seen: errors.append(f"duplicate sample_id {row['sample_id']}")
            seen.add(row["sample_id"])
            sequence_field = "reference_sequence" if track == "design" else "sequence"
            length_field = "reference_sequence_length" if track == "design" else "sequence_length"
            sequence = row.get(sequence_field, "")
            if not pattern.fullmatch(sequence): errors.append(f"{row['sample_id']}: invalid {sequence_field}")
            if row.get(length_field) != len(sequence): errors.append(f"{row['sample_id']}: {length_field} mismatch")
            if track == "design":
                if "sequence" in row: errors.append(f"{row['sample_id']}: design sequence must not be exposed as model input")
                if row.get("reference_usage") != "audit_only_not_model_input": errors.append(f"{row['sample_id']}: missing reference usage guard")
            identity = row.get("max_historical_sequence_identity")
            if manifest["status"] == "official_candidate" and (identity is None or identity >= manifest["homology"]["threshold_exclusive"]):
                errors.append(f"{row['sample_id']}: failed formal homology gate")
    if manifest["status"] == "provisional": warnings.append("provisional build: homology was not verified")
    report = {"valid": not errors, "errors": errors, "warnings": warnings, "sample_ids": len(seen)}
    print(json.dumps(report, indent=2))
    if errors: raise SystemExit(1)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m proteinarena_repro")
    sub = p.add_subparsers(required=True)
    f = sub.add_parser("fetch"); f.add_argument("--profile", type=Path, required=True); f.add_argument("--limit", type=int); f.set_defaults(func=cmd_fetch)
    h = sub.add_parser("prepare-homology"); h.add_argument("--profile", type=Path, required=True); h.set_defaults(func=cmd_prepare)
    b = sub.add_parser("build"); b.add_argument("--profile", type=Path, required=True); b.add_argument("--homology-tsv", type=Path); b.add_argument("--homology-complete-marker", type=Path); b.add_argument("--allow-unfiltered", action="store_true"); b.set_defaults(func=cmd_build)
    v = sub.add_parser("validate"); v.add_argument("--dataset", type=Path, required=True); v.set_defaults(func=cmd_validate)
    return p


def main() -> None:
    args = parser().parse_args()
    args.func(args)
