"""Re-index all chunks with the current embedding provider.

Run this whenever EMBEDDING_PROVIDER or EMBEDDING_DIM changes to make all
stored embeddings consistent with the current configuration.
"""
import sys
sys.path.insert(0, ".")

from models import db
from services import rag_service
from config import config

print(f"Re-indexing with provider={config.EMBEDDING_PROVIDER}, dim={config.EMBEDDING_DIM}")

chunks_col = db.chunks()
total = chunks_col.count_documents({})
print(f"Total chunks to re-index: {total}")

BATCH = 50
processed = 0
cursor = chunks_col.find({}, {"_id": 1, "text": 1})

batch_ids = []
batch_texts = []

def flush(batch_ids, batch_texts):
    embeddings = rag_service.embed_texts(batch_texts)
    for doc_id, emb in zip(batch_ids, embeddings):
        chunks_col.update_one({"_id": doc_id}, {"$set": {"embedding": emb}})
    return len(batch_ids)

for doc in cursor:
    batch_ids.append(doc["_id"])
    batch_texts.append(doc["text"])
    if len(batch_ids) >= BATCH:
        n = flush(batch_ids, batch_texts)
        processed += n
        batch_ids, batch_texts = [], []
        print(f"  {processed}/{total} done...")

if batch_ids:
    processed += flush(batch_ids, batch_texts)

print(f"Done. Re-indexed {processed} chunks with dim={config.EMBEDDING_DIM}.")
