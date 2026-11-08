"""Stable JSON digest for exactly what was approved (no Django dependency)."""
import hashlib
import json


def snapshot_digest(payload):
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
