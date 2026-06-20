"""Prune the vector store down to a canonical keep-list of documents.

Corpus-maintenance job: keep only the chunks belonging to the documents in
data/raw/ (the demo / evaluation corpus) and delete everything else that may
have accumulated in the store (e.g. ad-hoc uploads). Reuses the same factory
wiring + VectorStore.delete_except() the app uses — no direct SDK access here.

SAFE BY DEFAULT — a plain run only *reports* what it would delete:
    python -m scripts.prune_corpus            # dry run (no changes)
    python -m scripts.prune_corpus --yes      # actually delete

The keep-list is derived from the PDF filenames in data/raw/, which match the
`source_file` stored on each chunk at ingest time.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from app.core.factory import get_vector_store

RAW_DIR = Path("data/raw")


def main() -> None:
    apply = "--yes" in sys.argv[1:]

    keep = sorted(p.name for p in RAW_DIR.glob("*.pdf"))
    if not keep:
        print(f"No PDFs in {RAW_DIR}/ — refusing to prune (that would wipe everything).")
        return

    store = get_vector_store()
    counts = Counter(c.source_file for c in store.all_chunks())
    if not counts:
        print("Collection is empty — nothing to prune.")
        return

    keep_set = set(keep)
    print("Keep-list (from data/raw/):")
    for name in keep:
        print(f"  KEEP    {name:<24} ({counts.get(name, 0)} chunks in store)")

    doomed = {src: n for src, n in counts.items() if src not in keep_set}
    print()
    if not doomed:
        print("Nothing to delete - every stored chunk is in the keep-list.")
        return

    total = sum(doomed.values())
    print(f"Would DELETE {total} chunk(s) from {len(doomed)} document(s) not in the keep-list:")
    for src, n in sorted(doomed.items()):
        print(f"  DELETE  {src or '(no source_file)':<24} ({n} chunks)")

    if not apply:
        print("\nDry run — no changes made. Re-run with --yes to delete the above.")
        return

    deleted = store.delete_except(keep)
    print(f"\nDeleted {deleted} chunk(s). Kept the data/raw corpus.")


if __name__ == "__main__":
    main()
