from __future__ import annotations

import re
from collections.abc import Iterator

AA20 = set("ACDEFGHIKLMNPQRSTVWY")
EC_TO_CLASS = {
    "1": "oxidoreductase", "2": "transferase", "3": "hydrolase", "4": "lyase",
    "5": "isomerase", "6": "ligase", "7": "translocase",
}
PTM_TYPES = {"Modified residue", "Glycosylation", "Lipidation", "Cross-link", "Disulfide bond"}


def valid_sequence(entry: dict, max_length: int | None = None) -> bool:
    seq = entry.get("sequence", {}).get("value", "")
    return bool(seq) and set(seq) <= AA20 and (max_length is None or len(seq) <= max_length)


def xrefs(entry: dict, database: str) -> list[dict]:
    return [x for x in entry.get("uniProtKBCrossReferences", []) if x.get("database") == database]


def prop(xref: dict, key: str) -> str | None:
    for item in xref.get("properties", []):
        if item.get("key") == key:
            return item.get("value")
    return None


def comments(entry: dict, kind: str) -> list[str]:
    out = []
    for comment in entry.get("comments", []):
        if comment.get("commentType") != kind:
            continue
        out.extend(t.get("value", "") for t in comment.get("texts", []) if t.get("value"))
        for cofactor in comment.get("cofactors", []):
            name = cofactor.get("name")
            if name:
                out.append(name)
        for loc in comment.get("subcellularLocations", []):
            value = loc.get("location", {}).get("value")
            if value:
                out.append(value)
    return out


def interpro(entry: dict) -> list[tuple[str, str]]:
    pairs = []
    for item in xrefs(entry, "InterPro"):
        name = prop(item, "EntryName")
        if item.get("id") and name and name != "-":
            pairs.append((item["id"], name))
    return sorted(set(pairs))


def ec_numbers(entry: dict) -> list[str]:
    found = set()
    def walk(value: object) -> None:
        if isinstance(value, dict):
            if "ecNumber" in value and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", str(value["ecNumber"])):
                found.add(str(value["ecNumber"]))
            for item in value.get("ecNumbers", []):
                candidate = item.get("value") if isinstance(item, dict) else item
                if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", str(candidate)):
                    found.add(str(candidate))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(entry.get("proteinDescription", {}))
    walk(entry.get("comments", []))
    return sorted(found)


def cath_codes(entry: dict) -> list[str]:
    return sorted({x["id"] for x in xrefs(entry, "Gene3D") if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", x.get("id", ""))})


def _features(entry: dict, types: set[str]) -> list[dict]:
    return [f for f in entry.get("features", []) if f.get("type") in types]


def _ligand_text(feature: dict) -> str:
    parts = [feature.get("description", "")]
    for key in ("ligand", "ligandPart"):
        name = feature.get(key, {}).get("name")
        if name:
            parts.append(name)
    return "; ".join(x for x in parts if x)


def qa_labels(entry: dict) -> Iterator[tuple[str, str, list[str]]]:
    ecs = ec_numbers(entry)
    if ecs:
        yield "enzyme_classification", EC_TO_CLASS.get(ecs[0].split(".")[0], "enzyme"), [f"EC:{x}" for x in ecs]

    ipr = interpro(entry)
    if ipr:
        yield "functional_domains", "; ".join(name for _, name in ipr[:4]), [i for i, _ in ipr[:4]]

    go_mf = []
    for x in xrefs(entry, "GO"):
        term = prop(x, "GoTerm") or ""
        if term.startswith("F:"):
            go_mf.append((x["id"], term[2:]))
    if go_mf:
        yield "molecular_function", go_mf[0][1], [x for x, _ in go_mf]

    similarity = comments(entry, "SIMILARITY")
    if similarity:
        family = re.search(r"Belongs to the ([^.]+(?:family|group))", similarity[0], re.I)
        if family:
            yield "protein_family", family.group(1), similarity
        superfam = re.search(r"([^.]+superfamily)", similarity[0], re.I)
        if superfam:
            yield "superfamily", superfam.group(1), similarity

    bindings = _features(entry, {"Binding site"})
    binding_text = [_ligand_text(f) for f in bindings]
    metal_pattern = r"zinc|iron|calcium|magnesium|manganese|copper|cobalt|nickel|metal|\bZn\b|\bFe\b|\bCa\b|\bMg\b|\bMn\b|\bCu\b|\bCo\b|\bNi\b"
    metals = [text for text in binding_text if re.search(metal_pattern, text, re.I)]
    if metals:
        yield "metal_binding", metals[0], metals

    joined = " ".join(comments(entry, "FUNCTION") + [p for _, p in go_mf])
    binds = []
    if re.search(r"DNA[- ]bind|binds? DNA", joined, re.I): binds.append("DNA-binding")
    if re.search(r"RNA[- ]bind|binds? RNA", joined, re.I): binds.append("RNA-binding")
    if binds:
        yield "nucleic_acid_binding", " and ".join(binds), [joined]

    subunit = comments(entry, "SUBUNIT")
    if subunit:
        state = next((s for s in ["monomer", "homodimer", "heterodimer", "homotetramer", "oligomer"] if re.search(s, " ".join(subunit), re.I)), None)
        if state:
            yield "oligomerization", state, subunit

    cofactors = comments(entry, "COFACTOR")
    small = [text for text in binding_text if text and text not in metals]
    if cofactors or small:
        evidence = cofactors + small
        yield "small_molecule_binding", evidence[0], evidence

    cleavage = _features(entry, {"Signal peptide", "Transit peptide", "Propeptide", "Peptide"})
    if cleavage:
        kinds = sorted({f["type"] for f in cleavage})
        yield "cleavage_sites", ", ".join(kinds), kinds

    ptms = _features(entry, PTM_TYPES)
    ptm_comments = comments(entry, "PTM")
    if ptms or ptm_comments:
        labels = sorted({f.get("description") or f["type"] for f in ptms})
        evidence = labels + ptm_comments
        yield "post_translational_modifications", "; ".join(evidence[:4]), evidence

    locations = comments(entry, "SUBCELLULAR LOCATION")
    if locations:
        yield "primary_localization", locations[0], locations

    signals = _features(entry, {"Signal peptide", "Transit peptide"})
    if signals:
        kinds = sorted({f["type"] for f in signals})
        yield "targeting_signals", ", ".join(kinds), kinds
    elif (locations
          and all(re.fullmatch(r"cytoplasm|cytosol", loc, re.I) for loc in locations)
          and not _features(entry, {"Transmembrane"})
          and entry.get("proteinDescription", {}).get("flag") != "Precursor"):
        yield "targeting_signals", "no annotated targeting signal", ["cytoplasmic localization", "no Signal peptide or Transit peptide feature"]

    tm = _features(entry, {"Transmembrane"})
    if tm:
        tm_type = "single-pass" if len(tm) == 1 else "multi-pass"
        yield "transmembrane_type", tm_type, [f"{len(tm)} annotated transmembrane region(s)"]
        yield "hydrophobicity", "highly hydrophobic membrane protein" if len(tm) > 1 else "mixed regions with one hydrophobic membrane segment", [f"{len(tm)} annotated transmembrane region(s)"]
        yield "structural_composition", "membrane protein", [f"{len(tm)} annotated transmembrane region(s)"]
    else:
        sec = _features(entry, {"Helix", "Beta strand"})
        helices = sum(1 for f in sec if f["type"] == "Helix")
        strands = sum(1 for f in sec if f["type"] == "Beta strand")
        if helices + strands >= 3:
            label = "all-alpha" if helices and not strands else "all-beta" if strands and not helices else "alpha/beta"
            yield "structural_composition", label, [f"annotated helices={helices}, beta_strands={strands}"]
