"""Knowledge-base integrity: SHA-256 manifest of approved course files.

A file only enters the vector DB if its hash matches the hash an admin approved.
The manifest is committed to git, so any change to it shows up in review.
"""
import hashlib
import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "data" / "manifest.json"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_manifest(manifest=MANIFEST):
    return json.loads(manifest.read_text()) if manifest.exists() else {}


def verify(path, manifest=MANIFEST):
    """True only if this exact file content was approved."""
    return load_manifest(manifest).get(Path(path).name) == sha256(path)


def approve(paths, manifest=MANIFEST):
    """Admin action: record the current hash of each file as trusted."""
    data = load_manifest(manifest)
    for p in paths:
        data[Path(p).name] = sha256(p)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
