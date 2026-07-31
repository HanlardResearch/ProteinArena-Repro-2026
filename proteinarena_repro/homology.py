from __future__ import annotations

from pathlib import Path
import json


def parse_mmseqs(path: Path) -> dict[str, float]:
    maxima: dict[str, float] = {}
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                raise ValueError(f"{path}:{line_no}: expected query, target, fident")
            value = float(fields[2])
            if value > 1:
                value /= 100.0
            if not 0 <= value <= 1:
                raise ValueError(f"{path}:{line_no}: identity outside [0,1]")
            maxima[fields[0]] = max(value, maxima.get(fields[0], 0.0))
    return maxima


def verify_complete_marker(path: Path, candidate_fasta: Path, candidate_sha256: str) -> dict:
    marker = json.loads(path.read_text(encoding="utf-8"))
    if marker.get("status") != "complete":
        raise ValueError("homology marker status is not complete")
    if marker.get("candidates_sha256") != candidate_sha256:
        raise ValueError("homology marker candidate hash does not match current candidates.fasta")
    if not marker.get("historical_sha256") or not marker.get("mmseqs_version"):
        raise ValueError("homology marker lacks historical hash or MMseqs2 version")
    return marker


def identity_bin(value: float, threshold: float) -> str:
    if value < threshold:
        return "lt30"
    if value < 0.50:
        return "30to50"
    if value < 0.70:
        return "50to70"
    return "70to100"
