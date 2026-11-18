import unittest
from unittest.mock import Mock, patch

from services import document_service, rag_service


class TestEmbeddingCache(unittest.TestCase):
    def setUp(self):
        with rag_service._EMBEDDING_CACHE_LOCK:
            rag_service._EMBEDDING_CACHE.clear()

    def tearDown(self):
        with rag_service._EMBEDDING_CACHE_LOCK:
            rag_service._EMBEDDING_CACHE.clear()

    def test_repeated_texts_use_the_cached_embedding(self):
        with patch.object(rag_service.config, "EMBEDDING_PROVIDER", "llama"), \
                patch.object(rag_service.config, "EMBEDDING_MODEL", "test-model"), \
                patch.object(
                    rag_service,
                    "_compute_embeddings",
                    return_value=[[0.1, 0.2], [0.3, 0.4]],
                ) as compute:
            first = rag_service.embed_texts(["previous question", "new question", "previous question"])
            second = rag_service.embed_texts(["previous question", "new question"])

        self.assertEqual(first, [[0.1, 0.2], [0.3, 0.4], [0.1, 0.2]])
        self.assertEqual(second, [[0.1, 0.2], [0.3, 0.4]])
        compute.assert_called_once_with(["previous question", "new question"])


class TestStoredEmbeddingDimensions(unittest.TestCase):
    def test_retrieval_deduplicates_repeated_chunks_from_uploaded_copies(self):
        rows = [
            {
                "_id": "copy-1",
                "text": "A stack follows last in first out order.",
                "embedding": [1.0, 0.0],
                "unit": 1,
                "doc_type": "notes",
                "document_id": "doc-1",
            },
            {
                "_id": "copy-2",
                "text": "A stack follows last in first out order.",
                "embedding": [1.0, 0.0],
                "unit": 1,
                "doc_type": "notes",
                "document_id": "doc-2",
            },
        ]
        chunk_collection = Mock()
        chunk_collection.distinct.return_value = ["doc-1", "doc-2"]
        chunk_collection.find.return_value = rows
        document_collection = Mock()
        document_collection.find.return_value = []

        with patch.object(rag_service.db, "chunks", return_value=chunk_collection), \
                patch.object(rag_service.db, "documents", return_value=document_collection), \
                patch.object(rag_service, "embed_text", return_value=[1.0, 0.0]):
            results = rag_service.retrieve("subject-id", "stack", unit=1, top_k=2)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["document_id"], "doc-1")

    def test_duplicate_check_reembeds_legacy_question_bank_vectors(self):
        row = {
            "_id": "legacy-question",
            "question": "Explain a primary key.",
            "embedding": [1.0, 0.0],
        }
        collection = Mock()
        collection.find.return_value = [row]

        with patch.object(rag_service.db, "question_bank", return_value=collection), \
                patch.object(rag_service, "embed_text", return_value=[1.0, 0.0, 0.0]), \
                patch.object(rag_service, "embed_texts", return_value=[[1.0, 0.0, 0.0]]):
            is_duplicate, score, matched = rag_service.is_duplicate(
                "subject-id", "Define a primary key."
            )

        self.assertTrue(is_duplicate)
        self.assertEqual(score, 1.0)
        self.assertEqual(matched, row["question"])
        collection.update_one.assert_called_once_with(
            {"_id": "legacy-question"},
            {"$set": {"embedding": [1.0, 0.0, 0.0]}},
        )

    def test_retrieval_reembeds_legacy_chunk_vectors(self):
        row = {
            "_id": "legacy-chunk",
            "text": "A primary key uniquely identifies each row.",
            "embedding": [1.0, 0.0],
            "unit": 1,
            "doc_type": "syllabus",
            "document_id": "doc-id",
        }
        collection = Mock()
        collection.distinct.return_value = ["doc-id"]
        collection.find.return_value = [row]
        document_collection = Mock()
        document_collection.find.return_value = []

        with patch.object(rag_service.db, "chunks", return_value=collection), \
                patch.object(rag_service.db, "documents", return_value=document_collection), \
                patch.object(rag_service, "embed_text", return_value=[1.0, 0.0, 0.0]), \
                patch.object(rag_service, "embed_texts", return_value=[[1.0, 0.0, 0.0]]):
            results = rag_service.retrieve("subject-id", "primary key", unit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], row["text"])
        collection.update_one.assert_called_once_with(
            {"_id": "legacy-chunk"},
            {"$set": {"embedding": [1.0, 0.0, 0.0]}},
        )

    def test_cosine_reports_dimension_mismatch_without_numpy_dot_error(self):
        with self.assertRaisesRegex(ValueError, "Embedding dimensions do not match"):
            rag_service.cosine([1.0, 0.0, 0.0], [1.0, 0.0])

    def test_retrieve_indexes_existing_documents_that_have_no_chunks(self):
        row = {
            "_id": "new-chunk",
            "text": "A primary key uniquely identifies each row.",
            "embedding": [1.0, 0.0, 0.0],
            "unit": 1,
            "doc_type": "syllabus",
            "document_id": "legacy-document",
        }
        chunk_collection = Mock()
        chunk_collection.distinct.return_value = []
        chunk_collection.find.return_value = [row]
        document_collection = Mock()
        document_collection.find.return_value = [{
            "_id": "legacy-document",
            "type": "syllabus",
            "extracted_text": "The uploaded course syllabus text.",
        }]

        with patch.object(rag_service.db, "chunks", return_value=chunk_collection), \
                patch.object(rag_service.db, "documents", return_value=document_collection), \
                patch.object(document_service, "chunk_text", return_value=[{"text": row["text"], "unit": 1}]), \
                patch.object(rag_service, "index_chunks", return_value=1) as index_chunks, \
                patch.object(rag_service, "embed_text", return_value=[1.0, 0.0, 0.0]):
            results = rag_service.retrieve(
                "subject-id", "primary key", unit=1, doc_types=["syllabus"]
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], row["text"])
        index_chunks.assert_called_once_with(
            "subject-id",
            "legacy-document",
            "syllabus",
            [{"text": row["text"], "unit": 1}],
        )


if __name__ == "__main__":
    unittest.main()
