from __future__ import annotations

import hashlib
import random
from collections import defaultdict

from .annotations import cath_codes, ec_numbers, interpro, qa_labels, valid_sequence
from .homology import identity_bin

QUESTIONS = {
    "enzyme_classification": ["Assign this protein's top-level enzyme class.", "What broad enzyme class best describes this sequence?"],
    "functional_domains": ["What functional domains are identified in this protein?", "Name the principal annotated domains in this sequence."],
    "molecular_function": ["Infer the most specific molecular-function category for this protein.", "What molecular activity is associated with this sequence?"],
    "protein_family": ["Which protein family does this sequence belong to?", "Identify the protein family represented by this sequence."],
    "superfamily": ["Assign the most plausible evolutionary superfamily membership.", "Which evolutionary superfamily best fits this protein?"],
    "metal_binding": ["Does this protein coordinate metal ions, and which metal is indicated?", "Identify the annotated metal-binding property of this sequence."],
    "nucleic_acid_binding": ["Does this protein bind DNA, RNA, or both?", "What type of nucleic acid binding is associated with this protein?"],
    "oligomerization": ["Infer the most probable oligomerization state for this protein.", "What is the annotated quaternary association of this sequence?"],
    "small_molecule_binding": ["Which small molecule or cofactor does this protein bind?", "Identify the annotated small-molecule binding property."],
    "cleavage_sites": ["What types of cleavage-related regions are present?", "Identify the annotated cleavage or processed-peptide signal."],
    "post_translational_modifications": ["What post-translational modifications are annotated?", "Identify the principal post-translational modification of this protein."],
    "primary_localization": ["Determine the principal subcellular compartment in which this protein is found.", "Where is this protein primarily localized?"],
    "targeting_signals": ["What targeting signal is present in this protein?", "Identify the annotated cellular-targeting sequence."],
    "hydrophobicity": ["What is the hydrophobic character of this protein?", "Describe this sequence's broad hydrophobicity pattern."],
    "structural_composition": ["What broad structural fold class does this protein belong to?", "Classify this protein's broad structural composition."],
    "transmembrane_type": ["Is this a transmembrane protein and what type?", "Classify this sequence as single-pass, multi-pass, or non-transmembrane."],
}


def _choice(sample_key: str, values: list[str], seed: int) -> str:
    digest = hashlib.sha256(f"{seed}:{sample_key}".encode()).digest()
    return values[int.from_bytes(digest[:4], "big") % len(values)]


def _base(entry: dict, track: str, suffix: str, identity: float | None, profile: dict) -> dict:
    acc = entry["primaryAccession"]
    return {
        "sample_id": f"{profile['profile']}:{track}:{acc}:{suffix}",
        "benchmark": profile["name"],
        "profile": profile["profile"],
        "track": track,
        "accession": acc,
        "first_public_date": entry.get("entryAudit", {}).get("firstPublicDate"),
        "sequence": entry["sequence"]["value"],
        "sequence_length": entry["sequence"]["length"],
        "max_historical_sequence_identity": identity,
        "homology_bin": identity_bin(identity, profile["primary_max_sequence_identity_exclusive"]) if identity is not None else "unverified",
        "source": {"database": "UniProtKB/Swiss-Prot", "url": f"https://rest.uniprot.org/uniprotkb/{acc}.json"},
        "builder_version": "0.1.0"
    }


def build_all(entries: list[dict], identities: dict[str, float] | None, profile: dict, allow_unfiltered: bool) -> dict[str, list[dict]]:
    tracks: dict[str, list[dict]] = {"general_qa": [], "ec": [], "cath": [], "design": []}
    for entry in entries:
        if not valid_sequence(entry):
            continue
        acc = entry.get("primaryAccession")
        identity = identities.get(acc, 0.0) if identities is not None else None
        if identity is None and not allow_unfiltered:
            continue
        if identity is not None and identity >= profile["primary_max_sequence_identity_exclusive"]:
            continue
        seq = entry["sequence"]["value"]
        for category, answer, evidence in qa_labels(entry):
            row = _base(entry, "general_qa", category, identity, profile)
            question = _choice(row["sample_id"], QUESTIONS[category], profile["random_seed"])
            row.update({"dimension": dimension(category), "category": category, "question": question,
                        "prompt": f"{question}\nThe protein is {seq}", "answer": answer,
                        "evidence": evidence, "label_origin": "current Swiss-Prot structured annotation/curator text"})
            tracks["general_qa"].append(row)
        ecs = ec_numbers(entry)
        for code in ecs if len(ecs) == 1 else []:
            row = _base(entry, "ec", code, identity, profile)
            row.update({"label": code, "prompt": f"Determine the most appropriate four-level EC number for the protein whose amino-acid sequence is provided. The protein is {seq}",
                        "answer_format": "x.x.x.x", "evidence": [f"Swiss-Prot EC {code}"]})
            tracks["ec"].append(row)
        caths = cath_codes(entry)
        for code in caths if len(caths) == 1 else []:
            row = _base(entry, "cath", code, identity, profile)
            row.update({"label": code, "prompt": f"Determine the most probable CATH hierarchical classification (x.x.x.x) for the provided protein sequence. The protein is {seq}",
                        "answer_format": "x.x.x.x", "evidence": [f"UniProt Gene3D cross-reference {code}"], "mapping_type": "Gene3D proxy"})
            tracks["cath"].append(row)
        ipr = interpro(entry)
        if ipr and len(seq) <= profile["max_sequence_length"]:
            names = [name for _, name in ipr]
            row = _base(entry, "design", "interpro", identity, profile)
            # Design is conditioned only on InterPro function labels.  The natural
            # Swiss-Prot sequence is retained for provenance/audit and must never be
            # represented as model input.
            row.pop("sequence")
            row.pop("sequence_length")
            row.update({"interpro": [{"id": i, "name": n} for i, n in ipr],
                        "prompt": "Generate a protein sequence for a novel protein that integrates the following function keywords: " + "; ".join(names) + ". The designed protein sequence is",
                        "output_constraint": "exactly one uppercase standard-amino-acid sequence, length <= 1024",
                        "reference_sequence": seq,
                        "reference_sequence_length": len(seq),
                        "reference_usage": "audit_only_not_model_input"})
            tracks["design"].append(row)
    tracks["general_qa"] = balance_qa(tracks["general_qa"], profile["qa_target_size"], profile["random_seed"])
    tracks["design"] = stable_limit(tracks["design"], profile["design_target_size"], profile["random_seed"])
    for key in tracks:
        tracks[key].sort(key=lambda x: x["sample_id"])
    return tracks


def dimension(category: str) -> str:
    if category in {"enzyme_classification", "functional_domains", "molecular_function", "protein_family", "superfamily"}: return "Function"
    if category in {"metal_binding", "nucleic_acid_binding", "oligomerization", "small_molecule_binding"}: return "Interaction and Binding"
    if category in {"cleavage_sites", "post_translational_modifications", "primary_localization", "targeting_signals"}: return "Location and Modification"
    if category == "hydrophobicity": return "Physicochemical Property"
    return "Structure"


def stable_limit(rows: list[dict], limit: int | None, seed: int) -> list[dict]:
    if limit is None or len(rows) <= limit:
        return rows
    return sorted(rows, key=lambda r: hashlib.sha256(f"{seed}:{r['sample_id']}".encode()).hexdigest())[:limit]


def balance_qa(rows: list[dict], total: int, seed: int) -> list[dict]:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_cat[row["category"]].append(row)
    cats = list(QUESTIONS)
    base, remainder = divmod(total, len(cats))
    chosen = []
    for index, cat in enumerate(cats):
        chosen.extend(stable_limit(by_cat[cat], base + (index < remainder), seed))
    return chosen
