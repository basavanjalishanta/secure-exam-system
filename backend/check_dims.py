"""Check embedding dimensions in MongoDB."""
import sys
sys.path.insert(0, ".")
from models import db

chunk = db.chunks().find_one({})
if chunk:
    emb = chunk.get("embedding", [])
    print("chunk embedding dim:", len(emb))
    print("subject_id:", chunk.get("subject_id"))
    print("doc_type:", chunk.get("doc_type"))
else:
    print("no chunks found")

total = db.chunks().count_documents({})
print("total chunks:", total)

# Sample across subjects
for sid in db.chunks().distinct("subject_id"):
    sample = db.chunks().find_one({"subject_id": sid})
    emb = sample.get("embedding", []) if sample else []
    print(f"  subject {sid}: dim={len(emb)}")
