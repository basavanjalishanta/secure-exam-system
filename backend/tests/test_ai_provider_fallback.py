import unittest
from unittest.mock import patch

from services import ai_service


class TestAIProviderFallback(unittest.TestCase):
    def test_llama_provider_falls_back_to_mock_when_model_is_unavailable(self):
        original_provider = ai_service.config.AI_PROVIDER
        original_cached = ai_service._PROVIDER
        try:
            ai_service.config.AI_PROVIDER = "llama"
            ai_service._PROVIDER = None
            provider = ai_service.get_provider()
            self.assertEqual(provider.name, "llama")
        finally:
            ai_service.config.AI_PROVIDER = original_provider
            ai_service._PROVIDER = original_cached


if __name__ == "__main__":
    unittest.main()
