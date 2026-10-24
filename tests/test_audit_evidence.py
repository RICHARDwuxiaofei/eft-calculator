"""Evidence hashes must survive Windows-to-GitHub newline normalization."""
import hashlib
import json
from pathlib import Path


def test_checked_in_audit_evidence_hashes():
    root = Path(__file__).resolve().parents[1]/"docs/audits/2026-10-25"
    hashes = json.loads((root/"evidence-sha256.json").read_text(encoding="utf-8"))
    assert len(hashes) >= 80
    for relative, expected in hashes.items():
        assert hashlib.sha256((root/relative).read_bytes()).hexdigest() == expected, relative
