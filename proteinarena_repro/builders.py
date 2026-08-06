from __future__ import annotations

import hashlib
import random
from collections import defaultdict

from .annotations import cath_codes, ec_numbers, interpro, qa_labels, valid_sequence
from .homology import identity_bin

QUESTIONS = {
    "enzyme_classification": [
        "Assign the top-level enzyme class for this protein.", "Which broad enzyme class best fits this sequence?",
        "Classify this protein as an oxidoreductase, transferase, hydrolase, lyase, isomerase, ligase, translocase, or non-enzymatic.", "What is the highest-level EC class represented by this protein?",
        "Determine the principal enzyme class associated with the sequence.", "Identify the broad catalytic class of this protein.",
        "Which top-level enzyme category should be assigned here?", "From the sequence annotation, what enzyme class is indicated?",
        "Report the protein's first-level enzyme classification.", "What is the most appropriate broad EC class for this protein?",
        "Does this sequence indicate an enzyme, and if so which top-level class?", "Choose the best top-level enzyme class for this sequence.",
        "What catalytic superclass does this protein belong to?", "Give the protein's coarse enzyme classification.",
        "Which of the seven top-level enzyme classes applies to this protein?", "Infer the broad EC category associated with this sequence.",
        "State the principal enzyme class, or non-enzymatic status, for this protein.", "What top-level catalytic class is supported for the sequence?",
        "Assign the sequence to its broadest enzyme class.", "Identify the first-level enzyme category for this protein.",
    ],
    "functional_domains": [
        "What functional domains are identified in this protein?", "Name the principal annotated domains in this sequence.",
        "Which functional domains are assigned to the protein?", "List the main domains associated with this sequence.",
        "What domain annotations are present for this protein?", "Identify the protein's annotated functional domain regions.",
        "Which InterPro-style domains are reported for this sequence?", "Summarize the principal functional domains of the protein.",
        "What are the key domain assignments for this protein?", "Report the functional domain annotations linked to this sequence.",
        "Which domains does the protein contain according to its annotation?", "Identify the main domain families represented here.",
        "What functional domain signatures are associated with this sequence?", "Give the annotated domains for the protein.",
        "Which protein domains are most relevant to its function?", "What domain-level functional annotations are available?",
        "List the reported functional domains in this protein sequence.", "Determine the principal domains identified for this protein.",
        "What functional domain labels should be assigned to this sequence?", "Name the sequence's annotated functional domains.",
    ],
    "molecular_function": [
        "Infer the most specific molecular-function category for this protein.", "What molecular activity is associated with this sequence?",
        "Which molecular function best describes this protein?", "Assign the most specific molecular-function term supported here.",
        "What is this protein's primary molecular activity?", "Identify the molecular function of the sequence.",
        "Which GO molecular-function category applies to this protein?", "What molecular role is annotated for this protein?",
        "Determine the most precise molecular function associated with the sequence.", "How should this protein's molecular function be described?",
        "Report the principal molecular-function annotation for this protein.", "What biochemical molecular activity does this sequence represent?",
        "Choose the best molecular-function category for the protein.", "Which specific molecular function is linked to this sequence?",
        "State the annotated molecular activity of this protein.", "What molecular function is most strongly supported by the annotation?",
        "Classify the protein by its most specific molecular function.", "Identify the sequence's molecular-function term.",
        "What does this protein do at the molecular level?", "Give the best-supported molecular-function description.",
    ],
    "protein_family": [
        "Which protein family does this sequence belong to?", "Identify the protein family represented by this sequence.",
        "What family assignment is associated with this protein?", "Assign this sequence to its annotated protein family.",
        "Which protein family best matches the annotation?", "Report the family to which this protein belongs.",
        "What is the protein family's annotated name?", "Determine the sequence's family classification.",
        "Which family is represented by this protein sequence?", "Identify the principal protein family for this entry.",
        "What family-level assignment is supported for the protein?", "Name the family associated with this sequence.",
        "Which annotated family contains this protein?", "Give the most appropriate protein-family label.",
        "How is this protein classified at the family level?", "State the sequence's annotated protein family.",
        "What protein family is indicated by the record?", "Assign the family membership for this sequence.",
        "Which family does the protein belong to according to its annotation?", "Report the protein family represented here.",
    ],
    "superfamily": [
        "Assign the most plausible evolutionary superfamily membership.", "Which evolutionary superfamily best fits this protein?",
        "What superfamily assignment is associated with this sequence?", "Identify the protein's annotated evolutionary superfamily.",
        "Which homologous superfamily contains this protein?", "Report the sequence's superfamily classification.",
        "What is the principal evolutionary superfamily for this entry?", "Assign this protein to its annotated superfamily.",
        "Which superfamily is supported by the protein record?", "Determine the evolutionary superfamily represented here.",
        "Name the superfamily associated with this sequence.", "How should this protein be classified at superfamily level?",
        "Which homologous group or superfamily does the sequence belong to?", "Give the most appropriate superfamily label.",
        "What evolutionary superfamily is indicated for this protein?", "State the annotated superfamily membership.",
        "Identify the superfamily containing this protein sequence.", "Which superfamily assignment best describes the entry?",
        "Report the sequence's evolutionary superfamily.", "Assign the protein's superfamily membership from the annotation.",
    ],
    "metal_binding": [
        "Does this protein coordinate metal ions, and which metal is indicated?", "Identify the annotated metal-binding property of this sequence.",
        "Which metal ion, if any, is associated with this protein?", "Determine whether the protein binds a metal and name it.",
        "What metal-binding annotation is reported for this sequence?", "Does the protein coordinate a metal cofactor?",
        "Identify the metal involved in the protein's binding site.", "Which metal ion is supported by the annotation?",
        "Is metal coordination annotated for this protein, and of what type?", "Report the protein's metal-binding property.",
        "What metal does this sequence appear to bind according to its record?", "Determine the annotated ion-coordination behavior.",
        "Which metal-binding event is associated with the protein?", "State whether a metal ion is bound and which one.",
        "What is the most probable annotated metal for this protein?", "Identify any metal ion coordinated by the sequence.",
        "Does the record indicate metal binding? If so, specify the metal.", "Give the metal-binding annotation for this protein.",
        "Which metal-binding property should be assigned to this sequence?", "Report the supported metal ion association.",
    ],
    "nucleic_acid_binding": [
        "Does this protein bind DNA, RNA, or both?", "What type of nucleic acid binding is associated with this protein?",
        "Identify whether the sequence is DNA-binding, RNA-binding, both, or neither.", "Which nucleic-acid substrate does this protein bind?",
        "What nucleic-acid binding annotation applies to the protein?", "Does the protein interact with DNA or RNA?",
        "Determine the annotated nucleic-acid binding specificity.", "Is this sequence associated with DNA binding, RNA binding, or both?",
        "Report the protein's nucleic-acid interaction type.", "Which nucleic acid is recognized by this protein according to its annotation?",
        "Does the record support DNA binding or RNA binding?", "Classify the sequence's nucleic-acid binding behavior.",
        "What kind of nucleic-acid interaction is reported here?", "Identify the annotated DNA/RNA binding property.",
        "State whether this protein binds DNA, RNA, both, or no nucleic acid.", "Which nucleic-acid binding category best fits the entry?",
        "Determine the protein's DNA/RNA binding class.", "What nucleic-acid binding function is associated with this sequence?",
        "Report the supported nucleic-acid interaction for this protein.", "Assign the appropriate nucleic-acid binding label.",
    ],
    "oligomerization": [
        "Infer the most probable oligomerization state for this protein.", "What is the annotated quaternary association of this sequence?",
        "Is this protein monomeric, dimeric, or part of a higher-order complex?", "Determine the protein's oligomeric state.",
        "Which subunit organization is reported for this protein?", "What quaternary structure is associated with the sequence?",
        "Identify the annotated oligomerization behavior.", "Does the record describe a monomer, dimer, or larger assembly?",
        "Report the protein's subunit association.", "Which oligomerization state best matches this entry?",
        "How is this protein organized in its native complex?", "State the annotated quaternary association.",
        "What is the protein's reported assembly state?", "Assign the appropriate oligomerization label.",
        "Determine whether the protein forms a monomer, dimer, or oligomer.", "Which subunit state is supported by the annotation?",
        "Identify the sequence's annotated multimerization state.", "What oligomeric arrangement is reported for this protein?",
        "Give the most likely annotated quaternary organization.", "Report the protein's oligomerization class.",
    ],
    "small_molecule_binding": [
        "Which small molecule or cofactor does this protein bind?", "Identify the annotated small-molecule binding property.",
        "What small molecule is associated with this protein?", "Determine the protein's annotated cofactor or ligand.",
        "Which small-molecule interaction is reported for the sequence?", "Does this protein bind a cofactor, and which one?",
        "Identify the principal small-molecule binding annotation.", "What ligand or cofactor is linked to this protein?",
        "Report the annotated small-molecule association.", "Which small molecule does the protein recognize according to its record?",
        "Determine the relevant cofactor or ligand for this sequence.", "What small-molecule binding property should be assigned?",
        "Is a small molecule or cofactor annotated for this protein?", "Name the principal ligand associated with the entry.",
        "Which cofactor-binding behavior is supported by the annotation?", "State the protein's small-molecule interaction.",
        "What ligand/cofactor is reported for this sequence?", "Identify the annotated small-molecule partner.",
        "Give the most specific small-molecule binding description.", "Report whether and what small molecule this protein binds.",
    ],
    "cleavage_sites": [
        "What types of cleavage-related regions are present?", "Identify the annotated cleavage or processed-peptide signal.",
        "Which cleavage features are annotated for this protein?", "Does the sequence contain a signal peptide, propeptide, or cleavage region?",
        "Report the protein's annotated processing sites.", "What cleavage-related annotation applies to this sequence?",
        "Identify any signal peptide, propeptide, or peptide-processing feature.", "Which processed regions are present in the protein record?",
        "Determine the types of cleavage features associated with this sequence.", "What proteolytic or maturation signals are annotated?",
        "Is a cleavage site or processed peptide reported here?", "Name the cleavage-related regions in this protein.",
        "What sequence-processing features are supported by the annotation?", "Report the annotated peptide cleavage information.",
        "Which cleavage motif or processed segment is present?", "Determine whether this protein has an annotated processing signal.",
        "Identify the protein's signal-peptide or propeptide features.", "What cleavage/processing type should be assigned?",
        "State the annotated cleavage-related properties of this sequence.", "Give the principal protein-processing feature.",
    ],
    "post_translational_modifications": [
        "What post-translational modifications are annotated?", "Identify the principal post-translational modification of this protein.",
        "Which PTM features are reported for this sequence?", "What covalent post-translational changes are annotated?",
        "Determine the protein's annotated post-translational modifications.", "Does the record indicate phosphorylation, glycosylation, or another PTM?",
        "Report the PTM annotation associated with this protein.", "Which modified residues or PTM types are present?",
        "Identify any glycosylation, lipidation, cross-link, or other modification.", "What post-translational processing is reported for this sequence?",
        "Which covalent modifications should be assigned to the protein?", "State the principal PTM information in the record.",
        "Does this protein have annotated post-translational modifications?", "What modification types are associated with the sequence?",
        "List the main PTM features of this protein.", "Determine the supported post-translational modification class.",
        "Which residue-level modifications are annotated here?", "Report the protein's post-translational modification profile.",
        "What PTM-related evidence is present for this sequence?", "Give the annotated post-translational modification(s).",
    ],
    "primary_localization": [
        "Determine the principal subcellular compartment in which this protein is found.", "Where is this protein primarily localized?",
        "What is the protein's main subcellular location?", "Identify the principal cellular compartment for this sequence.",
        "Which subcellular localization is annotated for the protein?", "Report where this protein is mainly found in the cell.",
        "Determine the protein's primary cellular localization.", "What compartment contains this protein according to its annotation?",
        "Which cellular location best describes this protein?", "State the annotated principal subcellular location.",
        "Where does the protein predominantly reside?", "Identify the main cellular compartment associated with this entry.",
        "What is the primary localization annotation for this sequence?", "Report the protein's principal cellular distribution.",
        "In which subcellular compartment does this protein function?", "Assign the most appropriate primary localization.",
        "Which compartment is supported by the protein record?", "Determine where the sequence's protein product is localized.",
        "Give the principal subcellular location of this protein.", "What cellular compartment should be assigned to the entry?",
    ],
    "targeting_signals": [
        "What targeting signal is present in this protein?", "Identify the annotated cellular-targeting sequence.",
        "Does this protein contain a signal peptide or transit peptide?", "Which targeting signal, if any, is annotated here?",
        "Determine the protein's N-terminal targeting feature.", "What cellular-addressing signal is present in the sequence?",
        "Is a signal peptide, transit peptide, or no targeting signal indicated?", "Report the annotated targeting sequence feature.",
        "Identify any peptide that directs this protein to a cellular compartment.", "Which targeting signal applies to this protein?",
        "Does the sequence have an annotated secretion or organelle-targeting signal?", "State the protein's targeting-signal annotation.",
        "What signal peptide or transit peptide information is available?", "Determine whether a cellular targeting sequence is present.",
        "Which N-terminal targeting class best describes this protein?", "Report the signal responsible for cellular targeting.",
        "Is there an annotated signal peptide or transit peptide in this entry?", "Identify the protein's cellular targeting feature.",
        "Give the appropriate targeting-signal label for this sequence.", "What targeting peptide annotation is associated with the protein?",
    ],
    "hydrophobicity": [
        "What is the hydrophobic character of this protein?", "Describe this sequence's broad hydrophobicity pattern.",
        "How hydrophobic is the protein overall?", "Classify the sequence by its broad hydrophobic property.",
        "Does this protein have strongly hydrophobic regions?", "What hydrophobicity profile is associated with this sequence?",
        "Determine the protein's general hydrophobic character.", "Is the sequence mostly hydrophilic, mixed, or highly hydrophobic?",
        "Report the broad hydrophobic property of this protein.", "Which hydrophobicity class best describes this sequence?",
        "Identify whether the protein contains prominent hydrophobic segments.", "How should this sequence's hydrophobicity be characterized?",
        "What is the annotated or inferred hydrophobic pattern?", "Classify the protein's overall hydrophobic behavior.",
        "Does the sequence show membrane-like hydrophobicity?", "State the broad hydrophobicity category for this protein.",
        "Determine whether this protein is highly hydrophobic or largely hydrophilic.", "What hydrophobic regions are indicated for the sequence?",
        "Give the protein's broad hydrophobicity description.", "Which overall hydrophobicity label applies here?",
    ],
    "structural_composition": [
        "What broad structural fold class does this protein belong to?", "Classify this protein's broad structural composition.",
        "Which overall fold class best describes the sequence?", "Determine whether this protein is all-alpha, all-beta, alpha/beta, or another class.",
        "What broad secondary-structure composition is annotated?", "Assign the protein's coarse structural class.",
        "Which structural composition category applies to this protein?", "Report the sequence's broad fold composition.",
        "Is this protein predominantly alpha, beta, alpha/beta, or membrane?", "Identify the principal structural class for the entry.",
        "What overall architecture is supported for this protein?", "Determine the broad structural fold type.",
        "Which structural composition label best fits the sequence?", "State the protein's coarse fold category.",
        "How should this protein be classified by broad structure?", "Report the dominant structural composition indicated here.",
        "What fold-level class is associated with this sequence?", "Choose the most appropriate broad structural category.",
        "Identify the protein's overall structural composition.", "Give the sequence's broad fold-class assignment.",
    ],
    "transmembrane_type": [
        "Is this a transmembrane protein and what type?", "Classify this sequence as single-pass, multi-pass, or non-transmembrane.",
        "Does the protein contain transmembrane regions, and how many passes?", "Determine the protein's transmembrane topology class.",
        "Which membrane-spanning category applies to this sequence?", "Is this protein non-transmembrane, single-pass, or multi-pass?",
        "Report the annotated transmembrane type of the protein.", "How should this sequence be classified by membrane topology?",
        "Does the record indicate one, multiple, or no transmembrane regions?", "Identify the protein's membrane-spanning class.",
        "What transmembrane topology is associated with this sequence?", "Determine whether this is a single-pass or multipass membrane protein.",
        "State the annotated transmembrane-region category.", "Which topology label best fits this protein?",
        "Is a membrane-spanning segment present in the sequence?", "Classify the protein's transmembrane architecture.",
        "Report whether this protein is single-pass, multi-pass, or soluble.", "What membrane topology should be assigned here?",
        "Identify the broad transmembrane type for this protein.", "Give the sequence's annotated membrane-spanning classification.",
    ],
}

EC_TEMPLATES = [
    "Determine the complete four-level EC number for the protein sequence provided.", "What is the most likely EC classification (x.x.x.x) for this protein?",
    "Assign the protein's precise four-level Enzyme Commission number.", "Predict the full EC number represented by this amino-acid sequence.",
    "Which four-level EC identifier should be assigned to this sequence?", "Report the complete EC classification for the protein.",
    "Identify the enzyme's EC number to all four levels.", "What EC number best matches this protein sequence?",
    "Give the most appropriate four-part Enzyme Commission classification.", "Classify this protein using its complete EC number.",
    "Determine the specific EC entry associated with the sequence.", "State the protein's four-level catalytic classification.",
    "Which full EC code is supported for this amino-acid sequence?", "Infer the precise EC number for the provided protein.",
    "Assign an EC label in the format x.x.x.x.", "What is the protein's complete enzyme commission identifier?",
    "Predict the most specific four-level EC annotation.", "Identify the exact EC classification of this protein.",
    "Report the sequence's full EC number, including all four levels.", "Which EC number should this protein receive?",
]

CATH_TEMPLATES = [
    "Determine the complete four-level CATH classification for this protein sequence.", "What is the most probable CATH code (x.x.x.x) for this protein?",
    "Assign the protein's precise four-level CATH hierarchy.", "Predict the full CATH classification represented by this sequence.",
    "Which four-level CATH identifier should be assigned here?", "Report the complete CATH code for the protein.",
    "Identify the CATH class, architecture, topology, and homologous superfamily.", "What CATH number best matches this amino-acid sequence?",
    "Give the most appropriate four-part CATH classification.", "Classify this protein using its complete CATH hierarchy.",
    "Determine the specific CATH entry associated with the sequence.", "State the protein's four-level structural classification.",
    "Which full CATH code is supported for this protein sequence?", "Infer the precise CATH number for the provided sequence.",
    "Assign a CATH label in the format x.x.x.x.", "What is the protein's complete structural CATH identifier?",
    "Predict the most specific four-level CATH annotation.", "Identify the exact CATH hierarchy of this protein.",
    "Report the sequence's CATH number, including all four levels.", "Which CATH classification should this protein receive?",
]

DESIGN_TEMPLATES = [
    "Generate a novel protein sequence satisfying the following function keywords: {names}. The designed sequence is",
    "Design a new protein that integrates these InterPro functional keywords: {names}. Return the protein sequence:",
    "Create an amino-acid sequence for a novel protein with the requested functions: {names}. The sequence is",
    "Using the following functional constraints, generate a biologically plausible protein sequence: {names}. Output:",
    "Produce one novel protein sequence consistent with these InterPro annotations: {names}. Designed sequence:",
    "Construct a de novo protein fulfilling the following functional keyword set: {names}. The answer is",
    "Generate an original amino-acid sequence whose functional profile includes: {names}. Sequence:",
    "Design a biologically plausible protein from these function labels: {names}. Provide the designed sequence:",
    "Create one new protein sequence conditioned on the following InterPro terms: {names}. Output the sequence:",
    "Synthesize a novel protein satisfying all of these function keywords: {names}. The designed protein is",
    "Given these InterPro functional constraints, propose a complete protein sequence: {names}. Answer:",
    "Generate a de novo amino-acid sequence integrating the following annotations: {names}. Return:",
    "Design one complete protein sequence for the combined functions listed here: {names}. Sequence:",
    "Translate these functional keywords into a novel protein sequence: {names}. The output should be",
    "Create a new protein compatible with the following InterPro function requirements: {names}. Output:",
    "Produce a single designed protein sequence that reflects these constraints: {names}. The sequence is",
    "Generate a candidate functional protein from this keyword specification: {names}. Designed sequence:",
    "Build a novel protein sequence incorporating the following functional labels: {names}. Return the sequence:",
    "Propose one complete amino-acid sequence with the requested InterPro functions: {names}. Answer:",
    "Perform function-conditioned de novo protein design for these keywords: {names}. The designed sequence is",
]


def _choice(sample_key: str, values: list[str], seed: int) -> str:
    digest = hashlib.sha256(f"{seed}:{sample_key}".encode()).digest()
    return values[int.from_bytes(digest[:4], "big") % len(values)]


def _choice_with_index(sample_key: str, values: list[str], seed: int) -> tuple[int, str]:
    digest = hashlib.sha256(f"{seed}:{sample_key}".encode()).digest()
    index = int.from_bytes(digest[:4], "big") % len(values)
    return index, values[index]


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
            template_index, question = _choice_with_index(row["sample_id"], QUESTIONS[category], profile["random_seed"])
            row.update({"dimension": dimension(category), "category": category, "question": question,
                        "prompt": f"{question}\nThe protein is {seq}", "answer": answer,
                        "template_index": template_index, "template_count": len(QUESTIONS[category]),
                        "evidence": evidence, "label_origin": "current Swiss-Prot structured annotation/curator text"})
            tracks["general_qa"].append(row)
        ecs = ec_numbers(entry)
        for code in ecs if len(ecs) == 1 else []:
            row = _base(entry, "ec", code, identity, profile)
            template_index, template = _choice_with_index(row["sample_id"], EC_TEMPLATES, profile["random_seed"])
            row.update({"label": code, "prompt": f"{template}\nThe protein is {seq}",
                        "template_index": template_index, "template_count": len(EC_TEMPLATES),
                        "answer_format": "x.x.x.x", "evidence": [f"Swiss-Prot EC {code}"]})
            tracks["ec"].append(row)
        caths = cath_codes(entry)
        for code in caths if len(caths) == 1 else []:
            row = _base(entry, "cath", code, identity, profile)
            template_index, template = _choice_with_index(row["sample_id"], CATH_TEMPLATES, profile["random_seed"])
            row.update({"label": code, "prompt": f"{template}\nThe protein is {seq}",
                        "template_index": template_index, "template_count": len(CATH_TEMPLATES),
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
            template_index, template = _choice_with_index(row["sample_id"], DESIGN_TEMPLATES, profile["random_seed"])
            row.update({"interpro": [{"id": i, "name": n} for i, n in ipr],
                        "prompt": template.format(names="; ".join(names)),
                        "template_index": template_index, "template_count": len(DESIGN_TEMPLATES),
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
