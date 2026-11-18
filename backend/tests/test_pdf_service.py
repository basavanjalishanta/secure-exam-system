import unittest

from services import pdf_service


class TestAnswerKeyPdf(unittest.TestCase):
    def test_answer_key_preserves_question_numbering_and_escapes_model_text(self):
        question = {
            "index": 4,
            "full_question_num": 3,
            "sub_part": "a",
            "question": "Compare A & B when x < y.",
            "answer": "A < B & C.",
            "marks": 6,
        }

        self.assertEqual(pdf_service._answer_key_question_number(question, 5), "Q03(a)")
        pdf = pdf_service.build_answer_key_pdf({"subject_name": "A & B"}, [question])
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_answer_key_pdf_rejects_missing_answers(self):
        with self.assertRaisesRegex(ValueError, "has no generated answer"):
            pdf_service.build_answer_key_pdf(
                {"subject_name": "Data Structures"},
                [{"question": "Explain a stack."}],
            )

    def test_question_paper_pdf_escapes_question_and_metadata(self):
        pdf = pdf_service.build_question_paper_pdf(
            {"subject_name": "A & B", "subject_code": "CS<1>"},
            [{"question": "Compare A & B when x < y.", "marks": 6, "unit": 1}],
        )

        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
