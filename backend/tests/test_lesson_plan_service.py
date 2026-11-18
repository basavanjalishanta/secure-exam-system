import unittest
from unittest.mock import Mock, patch

from services import lesson_plan_service


class TestLessonPlanNormalization(unittest.TestCase):
    def test_normalizes_string_fields_and_structured_references(self):
        plan = lesson_plan_service.normalize_lesson_plan_data({
            "course_title": "Data Structures",
            "prerequisites": "1. Programming basics\n2. Discrete mathematics",
            "course_objectives": "1. Explain core structures\n2. Analyze algorithms",
            "course_outcomes": [
                "CO1: Explain foundational structures",
                {"code": "CO2", "description": "Analyze implementation", "bloom_level": "Analyze", "unit": "Unit 2"},
            ],
            "textbooks": "1. Data Structures by Author",
            "references": {"title": "Algorithms Reference", "author": "A. Writer"},
        })

        self.assertEqual(plan["prerequisites"], ["Programming basics", "Discrete mathematics"])
        self.assertEqual(plan["course_objectives"], ["Explain core structures", "Analyze algorithms"])
        self.assertEqual(plan["course_outcomes"][0]["co"], "CO1")
        self.assertEqual(plan["course_outcomes"][1]["unit"], 2)
        self.assertEqual(plan["textbooks"][0]["title"], "Data Structures by Author")
        self.assertEqual(plan["references"][0]["author"], "A. Writer")


class TestLessonPlanHourValidation(unittest.TestCase):
    def test_schedule_rejects_too_few_hours_without_looping(self):
        units = {unit: ["A topic"] for unit in range(1, 6)}

        with self.assertRaisesRegex(
            lesson_plan_service.LessonPlanInputError,
            "At least 10 contact hours",
        ):
            lesson_plan_service.build_lecture_schedule(units, total_hours=9)

    def test_generation_rejects_too_few_hours_before_calling_ai(self):
        subject_collection = Mock()
        subject_collection.find_one.return_value = {
            "name": "Data Structures",
            "units": [1, 2, 3, 4, 5],
        }
        documents_collection = Mock()
        documents_collection.find_one.return_value = {"extracted_text": "Unit 1: Arrays"}

        with patch.object(lesson_plan_service.db, "subjects", return_value=subject_collection), \
                patch.object(lesson_plan_service.db, "documents", return_value=documents_collection), \
                patch.object(lesson_plan_service.ai_service, "generate_lesson_plan_ai") as generate_ai:
            with self.assertRaisesRegex(lesson_plan_service.LessonPlanInputError, "At least 10 contact hours"):
                lesson_plan_service.generate_lesson_plan(
                    "507f1f77bcf86cd799439011",
                    meta={"total_contact_hours": 9},
                )

        generate_ai.assert_not_called()


if __name__ == "__main__":
    unittest.main()
