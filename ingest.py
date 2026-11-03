"""Admin script: build the vector DB from data/raw.

    python ingest.py                     # hash-check, chunk, embed, write index/
    python ingest.py --approve FILE ...  # trust these files' current hashes first
    python ingest.py --approve-all       # trust everything in data/raw (first setup only)

Files whose SHA-256 doesn't match data/manifest.json are skipped, so a swapped or
edited document can't poison the knowledge base without an explicit approval.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import docx
import faiss
from pypdf import PdfReader

from rag import integrity
from rag.retriever import INDEX_DIR, embed

DATA_DIR = Path(__file__).resolve().parent / "data" / "raw"
logging.getLogger("pypdf").setLevel(logging.ERROR)  # textbook math fonts spam warnings
CHUNK_WORDS, OVERLAP = 500, 50


def load_pages(path):
    """[(page_number or None, text)] for a PDF or DOCX."""
    if path.suffix.lower() == ".pdf":
        return [(i, page.extract_text() or "") for i, page in enumerate(PdfReader(path).pages, 1)]
    return [(None, "\n".join(p.text for p in docx.Document(path).paragraphs))]


def chunk_pages(pages, size=CHUNK_WORDS, overlap=OVERLAP):
    """Split into ~size-word chunks that remember their first and last page."""
    words = [(w, page) for page, text in pages for w in text.split()]
    chunks = []
    for start in range(0, max(len(words) - overlap, 1), size - overlap):
        part = words[start:start + size]
        if not part:
            break
        chunks.append({"text": " ".join(w for w, _ in part), "pages": [part[0][1], part[-1][1]]})
    return chunks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--approve", nargs="+", type=Path, metavar="FILE")
    ap.add_argument("--approve-all", action="store_true")
    args = ap.parse_args()

    files = sorted(p for p in DATA_DIR.glob("*") if p.suffix.lower() in (".pdf", ".docx"))
    if not files:
        sys.exit(f"No PDF/DOCX files in {DATA_DIR}")
    if args.approve_all:
        integrity.approve(files)
        print(f"Approved {len(files)} files")
    elif args.approve:
        integrity.approve(args.approve)
        print(f"Approved {len(args.approve)} files")

    chunks, skipped = [], []
    for f in files:
        if not integrity.verify(f):
            print(f"  SKIP {f.name}: hash not in manifest (changed or never approved)")
            skipped.append(f.name)
            continue
        file_chunks = chunk_pages(load_pages(f))
        for c in file_chunks:
            c["source"] = f.stem.strip()  # "Lecture 8_slides .pdf" has a stray space
        chunks += file_chunks
        print(f"  ok   {f.name}: {len(file_chunks)} chunks")
    if not chunks:
        sys.exit("Nothing verified to index.")

    vectors = embed([c["text"] for c in chunks])
    index = faiss.IndexFlatIP(vectors.shape[1])  # inner product on normalized vectors = cosine
    index.add(vectors)
    INDEX_DIR.mkdir(exist_ok=True)
    faiss.write_index(index, str(INDEX_DIR / "faiss.index"))
    (INDEX_DIR / "chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    print(f"Indexed {len(chunks)} chunks from {len(files) - len(skipped)} files; skipped {len(skipped)}.")


if __name__ == "__main__":
    main()
