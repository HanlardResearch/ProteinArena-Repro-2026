import unittest

from proteinarena_repro.builders import build_all


ENTRY = {
    "primaryAccession": "T0DESIGN",
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "entryAudit": {"firstPublicDate": "2026-01-02"},
    "uniProtKBCrossReferences": [
        {
            "database": "InterPro",
            "id": "IPR000001",
            "properties": [{"key": "EntryName", "value": "Test domain"}],
        }
    ],
    "sequence": {"value": "ACDEFGHIKLMNPQRSTVWY", "length": 20},
}

PROFILE = {
    "name": "ProteinArena-Repro-2026",
    "profile": "repro_2026",
    "primary_max_sequence_identity_exclusive": 0.3,
    "max_sequence_length": 1024,
    "qa_target_size": 0,
    "design_target_size": 870,
    "random_seed": 2026,
}


class DesignSchemaTest(unittest.TestCase):
    def test_natural_sequence_is_reference_not_model_input(self):
        row = build_all([ENTRY], {"T0DESIGN": 0.1}, PROFILE, False)["design"][0]
        self.assertNotIn("sequence", row)
        self.assertNotIn("sequence_length", row)
        self.assertEqual(row["reference_sequence"], ENTRY["sequence"]["value"])
        self.assertEqual(row["reference_sequence_length"], 20)
        self.assertEqual(row["reference_usage"], "audit_only_not_model_input")
        self.assertNotIn(row["reference_sequence"], row["prompt"])


if __name__ == "__main__":
    unittest.main()
