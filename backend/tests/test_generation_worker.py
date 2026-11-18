import unittest
from unittest.mock import patch

from services import generation_worker


class TestUniqueQuestionGeneration(unittest.TestCase):
    def setUp(self):
        self.subject = {"_id": "subject-id", "name": "Computer Science"}
        self.slot = {
            "unit": 1,
            "topic_hint": "file handling",
            "marks": 6,
            "difficulty": "Medium",
            "bloom_level": "Understand",
            "question_type": "Application",
        }

    def test_duplicate_is_rejected_and_added_to_the_next_prompt(self):
        duplicate = {"question": "Write a program to append data to a file."}
        unique = {"question": "Explain how buffered input improves file reading."}
        with patch.object(
            generation_worker.ai_service,
            "generate_questions",
            side_effect=[[duplicate], [unique]],
        ) as generate, patch.object(
            generation_worker.rag_service,
            "is_duplicate",
            side_effect=[(True, 0.97, "A stored question"), (False, 0.42, None)],
        ):
            result = generation_worker.generate_unique_question(
                subject=self.subject,
                slot=self.slot,
                context="File handling uses streams and buffers.",
                previous_questions=["A previous question"],
            )

        self.assertEqual(result["question"], unique["question"])
        self.assertFalse(result["duplicate"])
        self.assertEqual(generate.call_count, 2)
        self.assertIn(
            duplicate["question"],
            generate.call_args_list[1].kwargs["previous_questions"],
        )
        self.assertIn(
            "A stored question",
            generate.call_args_list[1].kwargs["variation_instruction"],
        )
        self.assertIn(
            "Keep the question focused on 'file handling'",
            generate.call_args_list[1].kwargs["variation_instruction"],
        )

    def test_duplicate_candidates_are_not_returned_after_retries(self):
        repeated = {"question": "Write a program to append data to a file."}
        with patch.object(
            generation_worker.ai_service,
            "generate_questions",
            return_value=[repeated],
        ), patch.object(
            generation_worker.rag_service,
            "is_duplicate",
            return_value=(True, 0.97, "A stored question"),
        ):
            result = generation_worker.generate_unique_question(
                subject=self.subject,
                slot=self.slot,
                context="File handling uses streams and buffers.",
                previous_questions=[],
                max_attempts=2,
            )

        self.assertIsNone(result)

    def test_requests_diverse_candidates_and_uses_unit_title(self):
        unique = {"question": "Describe how indexed allocation locates a file block."}
        subject = {
            **self.subject,
            "units": [{"unit": 1, "title": "File Organization"}],
        }
        with patch.object(
            generation_worker.ai_service,
            "generate_questions",
            return_value=[unique],
        ) as generate, patch.object(
            generation_worker.rag_service,
            "is_duplicate",
            return_value=(False, 0.31, None),
        ):
            result = generation_worker.generate_unique_question(
                subject=subject,
                slot={**self.slot, "topic_hint": None},
                context="Indexed allocation stores file block pointers.",
                previous_questions=[],
            )

        self.assertEqual(result["question"], unique["question"])
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(generate.call_args.kwargs["count"], 2)
        self.assertEqual(generate.call_args.kwargs["topic_hint"], "File Organization")

    def test_derives_a_real_unit_title_from_rag_context(self):
        question = {"question": "Explain structures and unions in C with an example."}
        subject = {
            **self.subject,
            "units": [{"unit": 1, "title": "Unit1"}],
        }
        with patch.object(
            generation_worker.ai_service,
            "generate_questions",
            return_value=[question],
        ) as generate, patch.object(
            generation_worker.rag_service,
            "is_duplicate",
            return_value=(False, 0.3, None),
        ):
            generation_worker.generate_unique_question(
                subject=subject,
                slot={**self.slot, "topic_hint": None},
                context="[Source 1 | notes | unit 1]\nUNIT - 1: Structures, Union and Files Outline :",
                previous_questions=[],
            )

        self.assertEqual(generate.call_args.kwargs["topic_hint"], "Structures, Union and Files")
        self.assertEqual(generate.call_args.kwargs["count"], 2)

    def test_topic_hints_are_assigned_round_robin_per_unit(self):
        plan = [
            {"unit": 1},
            {"unit": 2},
            {"unit": 1},
            {"unit": 1},
        ]

        generation_worker._assign_topic_hints(
            plan,
            {"1": "structures, unions", "2": "stacks"},
        )

        self.assertEqual(
            [slot.get("topic_hint") for slot in plan],
            ["structures", "stacks", "unions", "structures"],
        )

    def test_extracts_distinct_topics_from_ocr_outline_bullets(self):
        context = (
            "UNIT - 1: Structures, Union and Files Outline : "
            "\uf0a7 Structures \uf0a7 Union \uf0a7 Bitfields "
            "\uf0a7 Command Line Arguments \uf0a7 Files Structures Outline : "
            "\uf0a7 Definition \uf0a7 Defining a Structure "
            "\uf0a7 Declaring a Structure Variable \uf0a7 Nested Structure "
            "\uf0a7 Structures and Functions Structure Structure is an user-defined type."
        )

        topics = generation_worker._extract_topic_candidates(context)

        self.assertEqual(
            topics[:6],
            [
                "Structures",
                "Union",
                "Bitfields",
                "Command Line Arguments",
                "Files",
                "Defining a Structure",
            ],
        )
        self.assertIn("Structures and Functions", topics)
        self.assertNotIn("Structure is an user-defined type", topics)

    def test_auto_topic_hints_are_unique_per_slot_and_preserve_explicit_hints(self):
        plan = [
            {"unit": 1},
            {"unit": 1, "topic_hint": "user-selected topic"},
            {"unit": 1},
        ]

        generation_worker._assign_auto_topic_hints(
            plan,
            {1: ["Structures", "Union"]},
        )

        self.assertEqual(
            [slot.get("topic_hint") for slot in plan],
            ["Structures", "user-selected topic", "Union"],
        )

    def test_auto_topic_hints_prioritize_topics_not_seen_in_existing_questions(self):
        plan = [{"unit": 1}, {"unit": 1}]

        generation_worker._assign_auto_topic_hints(
            plan,
            {1: ["Structures", "Union", "Bitfields"]},
            ["Explain nested structures in C."],
        )

        self.assertEqual(
            [slot.get("topic_hint") for slot in plan],
            ["Union", "Bitfields"],
        )


if __name__ == "__main__":
    unittest.main()
