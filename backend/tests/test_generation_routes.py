import unittest
from unittest.mock import patch

from bson import ObjectId
from flask import Flask

from routes import answers, papers
from utils.security import create_access_token


class TestGenerationRoutes(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(answers.bp)
        self.app.register_blueprint(papers.bp)
        self.client = self.app.test_client()
        self.user = {
            "_id": ObjectId(),
            "email": "generation-test@example.invalid",
            "role": "lecturer",
            "name": "Generation test",
        }
        self.token = create_access_token(self.user)
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.subject = {
            "_id": ObjectId(),
            "name": "Data Structures",
            "code": "DS101",
            "selected_pattern": None,
        }

    def test_paper_creation_refuses_placeholder_answer_keys(self):
        with patch("utils.security.db.users") as users, patch.object(
            papers.db, "subjects"
        ) as subjects:
            users.return_value.find_one.return_value = self.user
            subjects.return_value.find_one.return_value = self.subject
            response = self.client.post(
                "/api/papers/generate",
                headers=self.headers,
                json={
                    "subject_id": str(self.subject["_id"]),
                    "questions": [{"question": "Explain a stack.", "marks": 6}],
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "Generate an answer for every question before creating the paper.",
        )

    def test_answer_route_rejects_malformed_question_before_model_call(self):
        with patch("utils.security.db.users") as users, patch.object(
            answers.db, "subjects"
        ) as subjects, patch.object(answers.ai_service, "generate_answer") as generate:
            users.return_value.find_one.return_value = self.user
            subjects.return_value.find_one.return_value = self.subject
            response = self.client.post(
                "/api/answers/generate",
                headers=self.headers,
                json={"subject_id": str(self.subject["_id"]), "questions": ["not a question object"]},
            )

        self.assertEqual(response.status_code, 400)
        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
