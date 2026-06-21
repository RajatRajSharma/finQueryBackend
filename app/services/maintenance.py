"""Corpus-maintenance service — prune the vector store to a canonical keep-list.

Shared by the CLI (scripts/prune_corpus.py) and the admin API (POST
/admin/prune). The keep-list is the PDF filenames in the raw dir; everything
else in the store is reported (dry run) or deleted (apply=True).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.core.interfaces import VectorStore


@dataclass
class PruneResult:
    """Outcome of a prune (dry-run or applied).

    `deleted_total`/`deleted_counts` are the chunks NOT in the keep-list — i.e.
    what was deleted when `applied` is True, or what *would* be deleted on a dry
    run. `kept_counts` maps each keep-list document to how many of its chunks
    are currently in the store (0 = listed in data/raw but not yet ingested).
    """

    applied: bool
    keep: list[str]
    kept_counts: dict[str, int]
    deleted_counts: dict[str, int]
    deleted_total: int


class CorpusPruner:
    def __init__(self, vector_store: VectorStore, raw_dir: Path) -> None:
        self._store = vector_store
        self._raw_dir = raw_dir

    def keep_list(self) -> list[str]:
        """The canonical keep-list: PDF filenames in the raw dir (== source_file)."""
        return sorted(p.name for p in self._raw_dir.glob("*.pdf"))

    def prune(self, apply: bool = False) -> PruneResult:
        """Report (apply=False) or perform (apply=True) the prune.

        Refuses to run if the keep-list is empty, so a missing/empty raw dir can
        never be used to wipe the whole collection.
        """
        keep = self.keep_list()
        if not keep:
            raise ValueError(
                "No PDFs in the raw dir - refusing to prune (that would wipe everything)."
            )
        counts = Counter(c.source_file for c in self._store.all_chunks())
        keep_set = set(keep)
        deleted_counts = {src: n for src, n in counts.items() if src not in keep_set}

        if apply and deleted_counts:
            self._store.delete_except(keep)

        return PruneResult(
            applied=apply,
            keep=keep,
            kept_counts={name: counts.get(name, 0) for name in keep},
            deleted_counts=dict(sorted(deleted_counts.items())),
            deleted_total=sum(deleted_counts.values()),
        )
