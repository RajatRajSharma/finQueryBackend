"""Prune the vector store down to a canonical keep-list of documents.

Corpus-maintenance job: keep only the chunks belonging to the documents in
data/raw/ (the demo / evaluation corpus) and delete everything else that may
have accumulated in the store (e.g. ad-hoc uploads). Thin CLI over the shared
CorpusPruner service — the same logic POST /admin/prune uses.

SAFE BY DEFAULT — a plain run only *reports* what it would delete:
    python -m scripts.prune_corpus            # dry run (no changes)
    python -m scripts.prune_corpus --yes      # actually delete

The keep-list is derived from the PDF filenames in data/raw/, which match the
`source_file` stored on each chunk at ingest time.
"""

from __future__ import annotations

import sys

from app.core.factory import get_corpus_pruner


def main() -> None:
    apply = "--yes" in sys.argv[1:]
    result = get_corpus_pruner().prune(apply=apply)

    print("Keep-list (from data/raw/):")
    for name in result.keep:
        print(f"  KEEP    {name:<24} ({result.kept_counts.get(name, 0)} chunks in store)")
    print()

    if not result.deleted_counts:
        print("Nothing to delete - every stored chunk is in the keep-list.")
        return

    verb = "DELETED" if result.applied else "Would DELETE"
    print(
        f"{verb} {result.deleted_total} chunk(s) from "
        f"{len(result.deleted_counts)} document(s) not in the keep-list:"
    )
    for src, n in result.deleted_counts.items():
        print(f"  DELETE  {src or '(no source_file)':<24} ({n} chunks)")

    if not result.applied:
        print("\nDry run — no changes made. Re-run with --yes to delete the above.")
    else:
        print("\nDone. Kept the data/raw corpus.")


if __name__ == "__main__":
    main()
