import unittest

from proteinarena_repro.builders import CATH_TEMPLATES, DESIGN_TEMPLATES, EC_TEMPLATES, QUESTIONS


class TemplateCoverageTest(unittest.TestCase):
    def test_every_subtask_has_at_least_twenty_templates(self):
        self.assertEqual(set(QUESTIONS), {
            "enzyme_classification", "functional_domains", "molecular_function", "protein_family",
            "superfamily", "metal_binding", "nucleic_acid_binding", "oligomerization",
            "small_molecule_binding", "cleavage_sites", "post_translational_modifications",
            "primary_localization", "targeting_signals", "hydrophobicity", "structural_composition",
            "transmembrane_type",
        })
        self.assertTrue(all(len(templates) >= 20 for templates in QUESTIONS.values()))
        self.assertGreaterEqual(len(EC_TEMPLATES), 20)
        self.assertGreaterEqual(len(CATH_TEMPLATES), 20)
        self.assertGreaterEqual(len(DESIGN_TEMPLATES), 20)
        for templates in (*QUESTIONS.values(), EC_TEMPLATES, CATH_TEMPLATES, DESIGN_TEMPLATES):
            self.assertEqual(len(templates), len(set(templates)))
