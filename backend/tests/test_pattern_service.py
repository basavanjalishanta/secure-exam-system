import unittest
from unittest.mock import patch

from services import pattern_service, validation_service


class TestPatternGenerationPlan(unittest.TestCase):
    def test_unit_or_pattern_generates_both_choices_for_each_subpart(self):
        pattern = pattern_service.default_patterns()[3]
        plan = pattern_service.build_generation_plan(pattern, [1, 2])

        self.assertEqual(len(plan), 12)
        self.assertEqual([slot["marks"] for slot in plan[:3]], [6, 6, 8])
        self.assertFalse(plan[0]["is_or"])
        self.assertTrue(plan[3]["is_or"])

    def test_unit_or_pattern_rejects_a_mismatched_unit_count(self):
        pattern = pattern_service.default_patterns()[3]

        with self.assertRaisesRegex(ValueError, "requires exactly 2 units"):
            pattern_service.build_generation_plan(pattern, [1, 2, 3])

    def test_unit_or_pattern_marks_and_validation_ignore_alternative_questions(self):
        pattern = pattern_service.default_patterns()[0]
        plan = pattern_service.build_generation_plan(pattern, [1, 2, 3, 4, 5])
        questions = [
            {
                **slot,
                "index": index,
                "question": f"Explain a distinct topic in unit {slot['unit']} part {index}.",
            }
            for index, slot in enumerate(plan)
        ]
        subject = {
            "_id": "subject-id",
            "units": [{"unit": unit} for unit in range(1, 6)],
        }

        with patch.object(
            validation_service.rag_service,
            "embed_texts",
            return_value=[[index, 1] for index in range(len(questions))],
        ), patch.object(
            validation_service.rag_service,
            "cosine",
            return_value=0,
        ), patch.object(
            validation_service.rag_service,
            "is_duplicate",
            return_value=(False, 0, None),
        ):
            result = validation_service.validate_paper(
                subject=subject,
                pattern=pattern,
                questions=questions,
            )

        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["summary"]["total_marks"], 100)

    def test_cie_unit_or_pattern_marks_match_generated_main_questions(self):
        pattern = pattern_service.default_patterns()[3]
        plan = pattern_service.build_generation_plan(pattern, [1, 2])
        total = sum(slot["marks"] for slot in plan if not slot["is_or"])

        self.assertEqual(pattern["total_marks"], total)

    def test_outdated_saved_unit_or_total_is_normalized(self):
        outdated = {
            **pattern_service.default_patterns()[3],
            "name": "CIE / Internals 50 Marks (2 Units, 6+6+8 OR Choice, Q1-Q4)",
            "total_marks": 50,
        }

        normalized = pattern_service.normalize_pattern(outdated)

        self.assertEqual(normalized["total_marks"], 40)
        self.assertIn("40 Marks", normalized["name"])
        self.assertEqual(normalized["sections"][0]["total"], 20)


if __name__ == "__main__":
    unittest.main()
