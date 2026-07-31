import unittest

from evaluate_gpt import (
    extract_protein_sequence,
    extract_response_text,
    hierarchy_correctness,
    parse_hierarchical_code,
    rep_n as eval_rep_n,
    summarize,
)
from proteinarena_repro.annotations import cath_codes, ec_numbers, qa_labels, valid_sequence
from proteinarena_repro.homology import identity_bin
from proteinarena_repro.metrics import rep_n


ENTRY = {
    "primaryAccession": "T0TEST",
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "entryAudit": {"firstPublicDate": "2026-01-02"},
    "proteinDescription": {"recommendedName": {"ecNumbers": [{"value": "2.7.7.60"}]}},
    "comments": [
        {"commentType": "SUBCELLULAR LOCATION", "subcellularLocations": [{"location": {"value": "Cytoplasm"}}]},
        {"commentType": "COFACTOR", "cofactors": [{"name": "Mg(2+)"}]}
    ],
    "features": [{"type": "Transmembrane", "description": "Helical"}],
    "uniProtKBCrossReferences": [
        {"database": "Gene3D", "id": "3.40.50.300"},
        {"database": "InterPro", "id": "IPR000001", "properties": [{"key": "EntryName", "value": "Test domain"}]}
    ],
    "sequence": {"value": "ACDEFGHIKLMNPQRSTVWY", "length": 20}
}


class CoreTest(unittest.TestCase):
    def test_labels(self):
        self.assertTrue(valid_sequence(ENTRY))
        self.assertEqual(ec_numbers(ENTRY), ["2.7.7.60"])
        self.assertEqual(cath_codes(ENTRY), ["3.40.50.300"])
        categories = {x[0] for x in qa_labels(ENTRY)}
        self.assertTrue({"enzyme_classification", "primary_localization", "small_molecule_binding", "transmembrane_type"} <= categories)

    def test_metrics_and_bins(self):
        self.assertEqual(identity_bin(0.2999, 0.3), "lt30")
        self.assertEqual(identity_bin(0.3, 0.3), "30to50")
        self.assertAlmostEqual(rep_n("AAAA", 2), 2 / 3)

    def test_gpt_response_parsers(self):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "EC 2.7.7.60"}],
                }
            ]
        }
        self.assertEqual(extract_response_text(response), ("EC 2.7.7.60", None))
        self.assertEqual(parse_hierarchical_code("EC 2.7.7.60"), "2.7.7.60")
        self.assertEqual(
            hierarchy_correctness("2.7.1.1", "2.7.7.60"),
            {
                "level_1_correct": True,
                "level_2_correct": True,
                "level_3_correct": False,
                "level_4_correct": False,
            },
        )

    def test_design_parser_and_summary(self):
        sequence = "ACDEFGHIKLMNPQRSTVWY"
        self.assertEqual(extract_protein_sequence(sequence), (sequence, True))
        self.assertEqual(extract_protein_sequence(f"```\n{sequence}\n```"), (sequence, False))
        rows = [
            {
                "sample_id": "d1",
                "track": "design",
                "status": "ok",
                "strict_format": True,
                "sequence_valid": True,
                "parsed_sequence": sequence,
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                "response_id": "resp_1",
            }
        ]
        summary = summarize(rows, [])
        self.assertEqual(summary["metrics"]["design"]["unique_fraction"], 1.0)
        self.assertEqual(summary["metrics"]["design"]["rep2_mean"], eval_rep_n(sequence, 2))
        self.assertEqual(summary["usage"]["total_tokens"], 30)


if __name__ == "__main__":
    unittest.main()
