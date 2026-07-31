from __future__ import annotations

from .annotations import AA20


def rep_n(sequence: str, n: int) -> float:
    grams = [sequence[i:i+n] for i in range(max(0, len(sequence) - n + 1))]
    return 0.0 if not grams else 1.0 - len(set(grams)) / len(grams)


def core_design_metrics(sequences: list[str]) -> dict:
    valid = [s for s in sequences if s and set(s) <= AA20 and len(s) <= 1024]
    return {
        "count": len(sequences),
        "valid_fraction": len(valid) / len(sequences) if sequences else 0.0,
        "rep2_mean": sum(rep_n(s, 2) for s in valid) / len(valid) if valid else None,
        "rep5_mean": sum(rep_n(s, 5) for s in valid) / len(valid) if valid else None,
        "unique_fraction": len(set(valid)) / len(valid) if valid else None,
    }

