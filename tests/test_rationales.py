import unittest

from proteinarena_repro.rationales import build_rationale


SEQUENCE = "MSTNPKPQRKTKRNTNRRPQDVKFPGGGQIVGGVLTALMALVAGASAACDEFGHIKLMNPQRSTVWY"


class RationaleTest(unittest.TestCase):
    def test_all_tracks_receive_model_style_rationales(self):
        rows = [
            {"track": "general_qa", "category": "metal_binding", "sequence": SEQUENCE,
             "answer": "zinc", "evidence": ["Zinc binding site"]},
            {"track": "ec", "sequence": SEQUENCE, "label": "2.7.7.60",
             "evidence": ["Swiss-Prot EC 2.7.7.60"]},
            {"track": "cath", "sequence": SEQUENCE, "label": "3.40.50.300",
             "evidence": ["UniProt Gene3D cross-reference 3.40.50.300"]},
            {"track": "design", "interpro": [{"id": "IPR000001", "name": "Test domain"}],
             "reference_sequence": SEQUENCE},
        ]
        for row in rows:
            rationale = build_rationale(row)
            self.assertGreater(len(rationale), 120)
            self.assertNotIn("UniProt", rationale)
            self.assertNotIn("Swiss-Prot", rationale)
            self.assertNotIn("IPR000001", rationale)
            self.assertNotIn("evidence field", rationale.lower())

    def test_design_rationale_does_not_expose_reference_sequence(self):
        row = {
            "track": "design",
            "interpro": [{"id": "IPR000001", "name": "Test domain"}],
            "reference_sequence": SEQUENCE,
        }
        rationale = build_rationale(row)
        self.assertNotIn(SEQUENCE, rationale)
        self.assertIn("Test domain", rationale)


if __name__ == "__main__":
    unittest.main()
