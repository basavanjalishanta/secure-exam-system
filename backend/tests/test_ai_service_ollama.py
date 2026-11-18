import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from services import ai_service


class TestOllamaService(unittest.TestCase):
    def test_ollama_provider_uses_configured_endpoint_and_parses_json(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
        )
        with patch("openai.OpenAI") as openai_client, \
                patch.object(ai_service.config, "OLLAMA_BASE_URL", "http://localhost:11434/v1"), \
                patch.object(ai_service.config, "OLLAMA_API_KEY", "ollama"), \
                patch.object(ai_service.config, "OLLAMA_MODEL", "test-model"), \
                patch.object(ai_service.config, "OLLAMA_TIMEOUT", 45), \
                patch.object(ai_service.config, "OLLAMA_TEMPERATURE", 0.3):
            openai_client.return_value.chat.completions.create.return_value = response
            provider = ai_service.OllamaProvider()

            result = provider.complete_json("system prompt", "user prompt", max_tokens=75)

        self.assertEqual(result, {"ok": True})
        openai_client.assert_called_once_with(
            base_url="http://localhost:11434/v1", api_key="ollama", timeout=45
        )
        openai_client.return_value.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=[
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
            max_tokens=75,
            extra_body={"repeat_penalty": 1.15, "num_predict": 75},
        )

    def test_ollama_connection_errors_are_actionable(self):
        provider = ai_service.OllamaProvider()
        provider.client = Mock()
        provider.client.chat.completions.create.side_effect = ConnectionError("connection refused")

        with self.assertRaisesRegex(ai_service.AIProviderError, "Could not reach Ollama"):
            provider.complete_json("system prompt", "user prompt")

    def test_ollama_empty_completion_is_reported_as_provider_error(self):
        provider = ai_service.OllamaProvider()
        provider.client = Mock()
        provider.client.chat.completions.create.return_value = SimpleNamespace(choices=[])

        with self.assertRaisesRegex(ai_service.AIProviderError, "no completion choices"):
            provider.complete_json("system prompt", "user prompt")

    def test_ollama_plain_text_answer_is_preserved_when_json_mode_misbehaves(self):
        provider = ai_service.OllamaProvider()
        provider.client = Mock()
        provider.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="A stack follows LIFO order."))]
        )

        result = provider.complete_json(
            "answer system prompt",
            json.dumps({"task": "answer"}),
        )

        self.assertEqual(result, {"answer": "A stack follows LIFO order."})

    def test_ollama_malformed_answer_json_salvages_the_model_answer_text(self):
        provider = ai_service.OllamaProvider()
        provider.client = Mock()
        provider.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"answer": "A stack follows LIFO order.'))]
        )

        result = provider.complete_json(
            "answer system prompt",
            json.dumps({"task": "answer"}),
        )

        self.assertEqual(result, {"answer": "A stack follows LIFO order."})

    def test_all_generation_functions_raise_provider_errors_without_mock_output(self):
        provider = Mock()
        provider.name = "ollama"
        provider.complete_json.side_effect = ai_service.AIProviderError("Ollama unavailable")
        with patch.object(ai_service, "get_provider", return_value=provider):
            with self.assertRaisesRegex(ai_service.AIProviderError, "Ollama unavailable"):
                ai_service.generate_questions(
                    subject={"name": "Computer Science"},
                    unit=1,
                    topic_hint="data structures",
                    count=1,
                    marks=5,
                    difficulty="Medium",
                    bloom="Understand",
                    qtype="Theory",
                    context="A linked list stores elements in nodes.",
                    previous_questions=[],
                )
            with self.assertRaisesRegex(ai_service.AIProviderError, "Ollama unavailable"):
                ai_service.generate_answer(
                    question={"question": "Explain linked lists", "marks": 5},
                    context="A linked list stores elements in nodes.",
                )
            with self.assertRaisesRegex(ai_service.AIProviderError, "Ollama unavailable"):
                ai_service.generate_lesson_plan_ai(
                    subject={"name": "Computer Science"},
                    syllabus_text="Data structures and algorithms",
                )

        self.assertEqual(provider.complete_json.call_count, 3)

    def test_generation_outputs_keep_structured_question_answer_and_plan_data(self):
        provider = Mock()
        provider.name = "ollama"
        provider.complete_json.side_effect = [
            {"questions": [{
                "question": "Explain how a linked list stores elements.",
                "unit": 1,
                "marks": 5,
                "difficulty": "Medium",
                "bloom_level": "Understand",
                "type": "Theory",
            }]},
            {"answer": "A linked list stores elements in nodes."},
            {"course_outcomes": [{"co": "CO1", "text": "Explain data structures."}]},
        ]
        with patch.object(ai_service, "get_provider", return_value=provider):
            questions = ai_service.generate_questions(
                subject={"name": "Computer Science"},
                unit=1,
                topic_hint="linked lists",
                count=1,
                marks=5,
                difficulty="Medium",
                bloom="Understand",
                qtype="Theory",
                context="A linked list stores elements in nodes.",
                previous_questions=[],
            )
            answer = ai_service.generate_answer(
                question={"question": "Explain linked lists", "marks": 5},
                context="A linked list stores elements in nodes.",
            )
            lesson_plan = ai_service.generate_lesson_plan_ai(
                subject={"name": "Computer Science"},
                syllabus_text="Data structures and algorithms",
            )

        self.assertEqual(questions[0]["question"], "Explain how a linked list stores elements.")
        self.assertEqual(questions[0]["question_type"], "Theory")
        self.assertEqual(answer, "A linked list stores elements in nodes.")
        self.assertEqual(lesson_plan["course_outcomes"][0]["co"], "CO1")

    def test_answer_generation_uses_answer_prompt_and_rejects_non_text_output(self):
        provider = Mock()
        provider.name = "ollama"
        provider.complete_json.return_value = {"answer": {"text": "not a string answer"}}
        with patch.object(ai_service, "get_provider", return_value=provider):
            with self.assertRaisesRegex(ai_service.AIProviderError, "invalid answer format"):
                ai_service.generate_answer(
                    question={"question": "Explain a primary key.", "marks": "6 marks"},
                    context="A primary key uniquely identifies each row in a database table.",
                )

        self.assertIn("model answer", provider.complete_json.call_args.args[0])

    def test_question_generation_normalizes_labeled_bloom_and_numeric_fields(self):
        provider = Mock()
        provider.name = "ollama"
        provider.complete_json.return_value = {"questions": [{
            "question": "Define a primary key in a relational database.",
            "unit": "Unit 2",
            "marks": "2 marks",
            "bl": "Remember",
            "co": "CO2",
            "po": "PO3",
            "pso": "PSO2",
        }]}
        with patch.object(ai_service, "get_provider", return_value=provider):
            questions = ai_service.generate_questions(
                subject={"name": "Database Systems"},
                unit=2,
                topic_hint="primary keys",
                count=1,
                marks=2,
                difficulty="Easy",
                bloom="Understand",
                qtype="Theory",
                context="A primary key uniquely identifies each row.",
                previous_questions=[],
                variation_instruction="Choose a different named concept.",
            )

        request = json.loads(provider.complete_json.call_args.args[1])
        self.assertEqual(questions[0]["unit"], 2)
        self.assertEqual(questions[0]["marks"], 2)
        self.assertEqual(questions[0]["bloom_level"], "Remember")
        self.assertEqual(questions[0]["bl"], 1)
        self.assertEqual(questions[0]["co"], 2)
        self.assertEqual(questions[0]["po"], 3)
        self.assertEqual(questions[0]["pso"], 2)
        self.assertEqual(request["variation_instruction"], "Choose a different named concept.")

    def test_groq_provider_setting_is_rejected_instead_of_falling_back(self):
        with patch.object(ai_service.config, "AI_PROVIDER", "groq"):
            with self.assertRaisesRegex(ai_service.AIProviderError, "Unsupported AI_PROVIDER"):
                ai_service.get_provider()


if __name__ == "__main__":
    unittest.main()
