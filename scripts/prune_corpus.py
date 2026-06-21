"""Prune the vector store to the keep-list (PDFs in data/raw/), deleting all
other chunks. Thin CLI over the CorpusPruner service that POST /admin/prune uses.

Dry-run by default — only reports what it would delete:
    python -m scripts.prune_corpus            # dry run (no changes)
    python -m scripts.prune_corpus --yes      # actually delete

The keep-list matches the `source_file` stored on each chunk at ingest time.
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
