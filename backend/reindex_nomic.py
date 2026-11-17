import sys
sys.path.insert(0, ".")
from models import db
from services import rag_service
from config import config

print(f"Re-indexing chunks with provider={config.EMBEDDING_PROVIDER}, model={config.EMBEDDING_MODEL}, dim={config.EMBEDDING_DIM}")

chunks_col = db.chunks()
total = chunks_col.count_documents({})
print(f"Total chunks to re-index: {total}")

cursor = chunks_col.find({}, {"_id": 1, "text": 1})
batch_ids = []
batch_texts = []
processed = 0

for doc in cursor:
    batch_ids.append(doc["_id"])
    batch_texts.append(doc["text"])
    if len(batch_ids) >= 20:
        embs = rag_service.embed_texts(batch_texts)
        for did, emb in zip(batch_ids, embs):
            chunks_col.update_one({"_id": did}, {"$set": {"embedding": emb}})
        processed += len(batch_ids)
        print(f"  {processed}/{total} re-indexed with 768-dim...")
        batch_ids, batch_texts = [], []

if batch_ids:
    embs = rag_service.embed_texts(batch_texts)
    for did, emb in zip(batch_ids, embs):
        chunks_col.update_one({"_id": did}, {"$set": {"embedding": emb}})
    processed += len(batch_ids)

print(f"Done. Successfully re-indexed {processed} chunks with nomic-embed-text (dim={len(embs[0]) if embs else 768})")
