#!/usr/bin/env python3
"""Build a deterministic 40-sample source-pair audit artifact."""

from __future__ import annotations

import hashlib
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proteinarena_repro.annotations import cath_codes, ec_numbers, interpro, qa_labels  # noqa: E402


TRACKS = ("general_qa", "ec", "cath", "design")
TRACK_LABELS = {
    "general_qa": "General Protein QA",
    "ec": "EC Prediction",
    "cath": "CATH Prediction",
    "design": "Functional De Novo Design",
}
QA_SOURCE_PATHS = {
    "enzyme_classification": ["proteinDescription", "comments[*].ecNumber"],
    "functional_domains": ["uniProtKBCrossReferences[database=InterPro]"],
    "molecular_function": ["uniProtKBCrossReferences[database=GO, GoTerm=F:*]"],
    "protein_family": ["comments[commentType=SIMILARITY]"],
    "superfamily": ["comments[commentType=SIMILARITY]"],
    "metal_binding": ["features[type=Binding site]"],
    "nucleic_acid_binding": ["comments[commentType=FUNCTION]", "GO molecular-function cross-references"],
    "oligomerization": ["comments[commentType=SUBUNIT]"],
    "small_molecule_binding": ["comments[commentType=COFACTOR]", "features[type=Binding site]"],
    "cleavage_sites": ["features[type=Signal peptide|Transit peptide|Propeptide|Peptide]"],
    "post_translational_modifications": ["features[type=Modified residue|Glycosylation|Lipidation|Cross-link|Disulfide bond]", "comments[commentType=PTM]"],
    "primary_localization": ["comments[commentType=SUBCELLULAR LOCATION]"],
    "targeting_signals": ["features[type=Signal peptide|Transit peptide]", "comments[commentType=SUBCELLULAR LOCATION]"],
    "hydrophobicity": ["features[type=Transmembrane]"],
    "structural_composition": ["features[type=Transmembrane|Helix|Beta strand]"],
    "transmembrane_type": ["features[type=Transmembrane]"],
}


def read_jsonl(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def rank(value: str) -> str:
    return hashlib.sha256(f"pair-audit-2026:{value}".encode()).hexdigest()


def select_rows(track: str, rows: list[dict], count: int = 10) -> list[dict]:
    if track != "general_qa":
        selected = []
        seen_accessions = set()
        for row in sorted(rows, key=lambda item: rank(item["sample_id"])):
            if row["accession"] in seen_accessions:
                continue
            selected.append(row)
            seen_accessions.add(row["accession"])
            if len(selected) == count:
                break
        return selected

    # QA is stratified so ten different categories are visible in the audit.
    by_category: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_category[row["category"]].append(row)
    categories = sorted(by_category, key=rank)[:count]
    return [min(by_category[category], key=lambda item: rank(item["sample_id"])) for category in categories]


def relation_for(track: str, row: dict, raw: dict) -> tuple[dict, list[str]]:
    sequence = raw.get("sequence", {}).get("value")
    checks = {
        "accession_matches": raw.get("primaryAccession") == row.get("accession"),
    }
    if track == "design":
        checks["reference_sequence_matches_raw"] = row.get("reference_sequence") == sequence
        checks["reference_hidden_from_model_input"] = "sequence" not in row and row.get("reference_sequence") not in row.get("prompt", "")
        raw_labels = [{"id": identifier, "name": name} for identifier, name in interpro(raw)]
        checks["interpro_constraints_match_raw"] = row.get("interpro") == raw_labels
        paths = ["sequence.value", "uniProtKBCrossReferences[database=InterPro]"]
    elif track == "ec":
        checks["sequence_matches_raw"] = row.get("sequence") == sequence
        checks["gold_label_present_in_raw"] = row.get("label") in ec_numbers(raw)
        checks["single_unambiguous_label"] = len(ec_numbers(raw)) == 1
        paths = ["sequence.value", "proteinDescription", "comments[*].ecNumber"]
    elif track == "cath":
        checks["sequence_matches_raw"] = row.get("sequence") == sequence
        checks["gold_label_present_in_raw"] = row.get("label") in cath_codes(raw)
        checks["single_unambiguous_label"] = len(cath_codes(raw)) == 1
        paths = ["sequence.value", "uniProtKBCrossReferences[database=Gene3D]"]
    else:
        checks["sequence_matches_raw"] = row.get("sequence") == sequence
        extracted = [
            {"category": category, "answer": answer, "evidence": evidence}
            for category, answer, evidence in qa_labels(raw)
            if category == row.get("category")
        ]
        checks["category_reextracts_from_raw"] = bool(extracted)
        checks["answer_reextracts_from_raw"] = any(item["answer"] == row.get("answer") for item in extracted)
        checks["evidence_reextracts_from_raw"] = any(item["evidence"] == row.get("evidence") for item in extracted)
        paths = ["sequence.value", *QA_SOURCE_PATHS.get(row.get("category"), [])]
    return checks, paths


def main() -> None:
    release = ROOT / "data/releases/repro_2026"
    raw_path = ROOT / "data/raw/repro_2026_uniprot.jsonl"
    if not raw_path.exists():
        raw_path = ROOT / "data/raw/repro_2026_uniprot.jsonl.gz"
    raw_by_accession = {row["primaryAccession"]: row for row in read_jsonl(raw_path)}
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))

    items = []
    for track in TRACKS:
        for index, row in enumerate(select_rows(track, read_jsonl(release / f"{track}.jsonl")), start=1):
            raw = raw_by_accession.get(row["accession"])
            if raw is None:
                checks, paths = {"raw_record_found": False}, []
            else:
                checks, paths = relation_for(track, row, raw)
                checks = {"raw_record_found": True, **checks}
            items.append({
                "audit_id": f"{track}-{index:02d}",
                "track": track,
                "track_label": TRACK_LABELS[track],
                "accession": row["accession"],
                "consistent": all(checks.values()),
                "checks": checks,
                "source_paths": paths,
                "constructed_sample": row,
                "raw_source_record": raw,
            })

    output = {
        "title": "ProteinArena-Repro-2026 Source Pair Audit",
        "selection": "Deterministic SHA-256 sample; QA stratified across ten categories; ten unique accessions per other track.",
        "source": {
            "database": "UniProtKB/Swiss-Prot",
            "raw_path": "data/raw/repro_2026_uniprot.jsonl",
            "raw_sha256": manifest["input"]["raw_sha256"],
            "release_status": manifest["status"],
        },
        "summary": {
            "sampled": len(items),
            "consistent": sum(item["consistent"] for item in items),
            "by_track": {
                track: {
                    "sampled": sum(item["track"] == track for item in items),
                    "consistent": sum(item["track"] == track and item["consistent"] for item in items),
                }
                for track in TRACKS
            },
        },
        "items": items,
    }
    destination = ROOT / "data/audit/source_pair_audit.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(destination), "summary": output["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
