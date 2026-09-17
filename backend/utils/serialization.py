"""Helpers to make Mongo documents JSON-serializable."""
from datetime import datetime

from bson import ObjectId


def jsonify_doc(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [jsonify_doc(d) for d in doc]
    if isinstance(doc, dict):
        out = {}
        for k, v in doc.items():
            if k == "_id":
                out["id"] = str(v)
            elif k == "embedding":
                continue  # never ship raw vectors to the client
            elif k == "password_hash":
                continue
            else:
                out[k] = jsonify_doc(v)
        return out
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc
