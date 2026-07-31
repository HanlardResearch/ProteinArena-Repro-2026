import unittest

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


if __name__ == "__main__":
    unittest.main()
