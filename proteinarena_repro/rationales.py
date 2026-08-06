"""Short, sequence-grounded rationales for ProteinArena-Repro-2026.

These rationales are deliberately written as model-style hypotheses.  They use
the sequence and the task label to describe observable biochemical clues, but do
not expose UniProt field names, accession IDs, or database lookups as premises.
The gold answer is stated only at the end so the text can be used as a rationale
target rather than as an input feature.
"""

from __future__ import annotations

import re
from collections import Counter


def _best_window(sequence: str, residues: set[str], size: int = 8) -> str:
    if not sequence:
        return ""
    width = min(size, len(sequence))
    return max(
        (sequence[i : i + width] for i in range(len(sequence) - width + 1)),
        key=lambda window: sum(aa in residues for aa in window),
    )


def _features(sequence: str) -> dict[str, object]:
    seq = sequence or ""
    length = len(seq)
    counts = Counter(seq)
    if not length:
        return {"length": 0, "hydro": 0.0, "charged": 0.0, "polar": 0.0, "cys": 0, "glypro": 0.0, "low": 0.0, "tm_windows": 0, "nxs": 0, "nterm": "", "polar_window": "", "basic_window": "", "metal_window": "", "hydro_window": ""}
    hydrophobic = set("AILMFWVY")
    charged = set("DEKR")
    polar = set("STNQDEKRH")
    tm_windows = 0
    # A soft, interpretable membrane-like heuristic; it is not a predictor.
    for i in range(max(0, length - 20 + 1)):
        window = seq[i : i + 20]
        if sum(a in hydrophobic for a in window) >= 14 and sum(a in "DEKR" for a in window) <= 2:
            tm_windows += 1
    return {
        "length": length,
        "hydro": sum(counts[a] for a in hydrophobic) / length,
        "charged": sum(counts[a] for a in charged) / length,
        "polar": sum(counts[a] for a in polar) / length,
        "cys": counts["C"],
        "glypro": (counts["G"] + counts["P"]) / length,
        "low": max(counts.values()) / length,
        "tm_windows": tm_windows,
        "nxs": len(re.findall(r"N[^P][ST]", seq)),
        "nterm": seq[: min(12, length)],
        "polar_window": _best_window(seq, set("STNQDEKRH")),
        "basic_window": _best_window(seq, set("KRH")),
        "metal_window": _best_window(seq, set("CHDE")),
        "hydro_window": _best_window(seq, hydrophobic, 12),
    }


def _composition(f: dict[str, object]) -> str:
    hydro = float(f["hydro"])
    charged = float(f["charged"])
    if hydro >= 0.52:
        return "a hydrophobic composition that can support a membrane-facing or buried core"
    if charged >= 0.22:
        return "a relatively charged composition that is compatible with solvent exposure and polar contacts"
    return "a mixed composition with both hydrophobic-core and polar-surface residues"


def _ec_hierarchy(code: str) -> tuple[str, str, str]:
    parts = (code or "").split(".")
    top = {
        "1": "oxidoreductases", "2": "transferases", "3": "hydrolases",
        "4": "lyases", "5": "isomerases", "6": "ligases", "7": "translocases",
    }.get(parts[0] if parts else "", "enzymes")
    prefix2 = ".".join(parts[:2])
    prefix3 = ".".join(parts[:3])
    # EC subclass meanings depend on the top-level class.  Keep uncommon paths
    # numeric rather than inventing a class-independent chemical description.
    second = {
        "2.7": "transferases that move phosphorus-containing groups",
    }.get(prefix2, f"EC subclass {prefix2}, which narrows the reaction type")
    third = {
        "2.7.7": "nucleotidyltransferases",
    }.get(prefix3, f"EC sub-subclass {prefix3}, which refines donor and substrate chemistry")
    return top, second, third


def _cath_hierarchy(code: str) -> tuple[str, str, str, str]:
    parts = (code or "").split(".")
    names = [
        "overall fold class", "architecture", "topology or fold arrangement", "homologous superfamily"
    ]
    return tuple(f"{name} {value}" for name, value in zip(names, parts + ["?"] * 4))  # type: ignore[return-value]


def _answer(row: dict) -> str:
    return str(row.get("answer") or row.get("label") or "the annotated class")


def build_rationale(row: dict) -> str:
    """Return one concise English rationale for a generated benchmark row."""
    track = row.get("track", "general_qa")
    if track == "design":
        names = [str(item.get("name", "")).strip() for item in row.get("interpro", []) if item.get("name")]
        target = "; ".join(names) or "the requested functional constraints"
        return (
            f"The design brief asks for a novel protein integrating {target}. "
            "I would translate these functional requirements into a compact fold with a hydrophobic core, "
            "a polar and charged surface for solvent and ligand contacts, and local residue patterns that can "
            "support the requested binding or catalytic roles. I would avoid long low-complexity runs and keep "
            "the chain within the allowed standard-amino-acid alphabet, while preserving enough sequence diversity "
            "to make the design non-identical to natural references. The output should therefore be one complete "
            "uppercase amino-acid sequence satisfying the requested functions."
        )

    sequence = str(row.get("sequence", ""))
    f = _features(sequence)
    length = int(f["length"])
    comp = _composition(f)
    answer = _answer(row)
    category = row.get("category", "")

    if track == "ec":
        top, second, third = _ec_hierarchy(answer)
        return (
            f"The sequence is {length} residues long and has {comp}. A soluble catalytic protein of this size "
            "can accommodate a defined substrate pocket, and the balance of polar, charged, and hydrophobic "
            f"residues is compatible with binding a chemically polar substrate; the local segment {f['polar_window']} "
            "is one plausible polar-contact region, although its role would require structural confirmation. The EC hierarchy places the "
            f"activity in {top}, specifically {second}, then {third}; the final serial number selects the "
            f"particular reaction within that branch. Therefore, the most likely EC number is {answer}."
        )

    if track == "cath":
        h1, h2, h3, h4 = _cath_hierarchy(answer)
        membrane_note = "The sequence does not look dominated by long membrane-like segments." if int(f["tm_windows"]) == 0 else "The sequence contains membrane-like hydrophobic segments that should be considered when interpreting its fold."
        return (
            f"At {length} residues, the sequence has {comp}. {membrane_note} These broad sequence-level clues "
            "are compatible with a compact, repeatedly conserved protein fold rather than an unstructured chain. "
            f"The hierarchical assignment is {h1}, {h2}, {h3}, and {h4}; together these levels identify the "
            f"most specific structural neighborhood. The predicted CATH/Gene3D-style code is therefore {answer}."
        )

    if category == "enzyme_classification":
        return (
            f"The protein is {length} residues long and shows {comp}. Its sequence has the mixed polar and "
            "hydrophobic character expected for a folded catalytic domain rather than a purely repetitive scaffold. "
            f"The local segment {f['polar_window']} provides one plausible polar reaction-site region, although its "
            "role would require structural confirmation. The likely chemistry is best summarized at the broad enzyme level, "
            f"where the reported catalytic class is {answer}."
        )
    if category == "functional_domains":
        return (
            f"The {length}-residue chain has {comp} and contains enough sequence complexity to form one or more "
            "structured domains. Local changes in polarity and hydrophobicity suggest boundaries between a buried "
            "core and exposed functional surfaces. These are the sequence-level clues expected for recognizable "
            f"domain signatures, so the principal domain assignment is {answer}."
        )
    if category == "molecular_function":
        return (
            f"The sequence length is {length} residues, with {comp}. A folded protein with this composition can "
            "present a chemically selective pocket or interaction surface; polar and charged residues would help "
            "recognize substrates, nucleic acids, or partner proteins. Combining these physical clues with the "
            f"most compatible molecular activity gives the answer: {answer}."
        )
    if category in {"protein_family", "superfamily"}:
        level = "family" if category == "protein_family" else "evolutionary superfamily"
        return (
            f"The chain is {length} residues long and has {comp}, a pattern compatible with a conserved folded "
            f"protein core and a variable interaction surface. Such conserved core chemistry is the main signal "
            f"used to group related homologs at the {level} level. The sequence is therefore most consistent with "
            f"the {level} assignment {answer}."
        )
    if category == "metal_binding":
        return (
            f"The {length}-residue sequence contains {int(f['cys'])} cysteine residues and {comp}. Cysteine, "
            f"histidine, and acidic residues can create a geometrically constrained coordination site; {f['metal_window']} "
            "is a plausible local coordinating region, while nearby "
            "polar residues can tune metal affinity. The observed sequence is consequently compatible with a "
            f"metal-binding site involving {answer}."
        )
    if category == "nucleic_acid_binding":
        return (
            f"The protein is {length} residues long and has a charged fraction of {float(f['charged']):.0%}. "
            f"The local segment {f['basic_window']} is enriched in basic side chains and could contribute to a "
            "positively biased surface that stabilizes the negatively charged phosphate backbone of a nucleic "
            "acid, while structured hydrophobic segments provide the supporting fold. This favors the annotated "
            f"nucleic-acid interaction class {answer}."
        )
    if category == "oligomerization":
        return (
            f"The {length}-residue chain has {comp}, suggesting a stable folded surface that can either pack "
            "against another subunit or remain solvent-exposed as a monomer. Repeated hydrophobic patches and "
            "charged interfaces are the sequence-level features expected to influence assembly. The most plausible "
            f"quaternary state is {answer}."
        )
    if category == "small_molecule_binding":
        return (
            f"At {length} residues, the sequence has {comp}. A small-molecule pocket generally combines buried "
            f"hydrophobic residues with polar or charged side chains; {f['polar_window']} is one candidate segment "
            "that could orient the ligand and stabilize its "
            "specific groups. This combination is compatible with the reported ligand/cofactor association, "
            f"namely {answer}."
        )
    if category == "cleavage_sites":
        return (
            f"The sequence begins as a {length}-residue precursor with {comp}. Cleavage or processing signals "
            "are often encoded as short terminal or internal segments that differ in polarity and hydrophobicity "
            "from the mature domain. The sequence-level interpretation is therefore consistent with the annotated "
            f"processing features: {answer}."
        )
    if category == "post_translational_modifications":
        return (
            f"The chain is {length} residues long and contains {int(f['cys'])} cysteines together with "
            f"{int(f['nxs'])} N-X-S/T-like sequons. These residues can provide chemically accessible sites for "
            "oxidation, glycosylation, lipid attachment, cross-linking, or other covalent changes, depending on "
            f"their structural context. The most compatible PTM description is {answer}."
        )
    if category == "primary_localization":
        return (
            f"The sequence has {comp} across {length} residues. The absence or presence of strongly hydrophobic "
            "segments, together with the balance of charged and polar residues, provides a coarse indication of "
            "whether the protein can remain soluble or associate with a membrane or organelle environment. These "
            f"clues are most consistent with the primary localization {answer}."
        )
    if category == "targeting_signals":
        if "no annotated" in answer.lower():
            return (
                f"The {length}-residue sequence starts with {f['nterm']}, which does not show a strong hydrophobic leader or a clear "
                f"transit-like composition; its overall profile is {comp}. A protein with these features can enter "
                "the cytosolic pool without a dedicated targeting peptide. Therefore, the most likely targeting-signal "
                f"interpretation is {answer}."
            )
        return (
            f"The sequence is {length} residues long and begins with {f['nterm']}. A targeting peptide is expected to be a short "
            "terminal segment with a distinctive hydrophobic or transit-compatible residue pattern followed by a "
            "more balanced mature region. The observed organization is consistent with the targeting annotation "
            f"{answer}."
        )
    if category == "hydrophobicity":
        return (
            f"The sequence is {length} residues long with an estimated hydrophobic-residue fraction of "
            f"{float(f['hydro']):.0%}; {f['hydro_window']} is among its most hydrophobic local stretches. "
            "Such segments tend to form a buried core or a membrane-facing helix, "
            "whereas polar and charged residues remain more exposed. This sequence-level balance supports the "
            f"hydrophobicity description {answer}."
        )
    if category == "structural_composition":
        return (
            f"The {length}-residue chain has {comp}. Helix-forming and strand-compatible residues are distributed "
            "throughout a sequence of sufficient complexity to support a stable secondary-structure framework. "
            "Hydrophobic packing would stabilize the interior while polar residues face solvent, leading to the "
            f"most likely structural composition {answer}."
        )
    if category == "transmembrane_type":
        windows = int(f["tm_windows"])
        if windows:
            state = "one dominant membrane-like segment" if windows < 4 else "multiple overlapping membrane-like segments"
            return (
                f"The sequence contains {state} under a simple hydrophobic-window check, with {f['hydro_window']} "
                "representing one highly hydrophobic local stretch, while charged residues "
                "are depleted within those stretches. This pattern is characteristic of membrane-spanning helices "
                f"rather than a uniformly soluble protein. The resulting transmembrane classification is {answer}."
            )
        return (
            f"The {length}-residue sequence has no extended strongly hydrophobic window under a conservative check "
            "and retains a mixed polar/charged composition. That makes a multi-pass membrane topology unlikely. "
            f"The most likely transmembrane interpretation is therefore {answer}."
        )
    return (
        f"The sequence is {length} residues long and has {comp}. These broad sequence-level features provide a "
        f"plausibility check for the requested annotation, leading to the answer {answer}."
    )
