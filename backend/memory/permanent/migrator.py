"""Legacy memory migration utilities."""

from typing import Optional, Dict, Any

import chromadb

from backend.core.logging import get_logger
from backend.config import CHROMADB_PATH
from .facade import PromotionCriteria

_log = get_logger("memory.migrator")


class LegacyMemoryMigrator:
    """Migrate data from old ChromaDB storage format."""

    def __init__(
        self,
        old_db_path: Optional[str] = None,
        new_long_term=None,
    ):
        """Initialize migrator.

        Args:
            old_db_path: Path to old ChromaDB storage
            new_long_term: Target LongTermMemory instance
        """
        db_path = old_db_path or str(CHROMADB_PATH)
        self.old_client = chromadb.PersistentClient(path=db_path)
        self.new_long_term = new_long_term

    def analyze_existing(self) -> Dict[str, Any]:
        """Analyze existing data for migration.

        Returns:
            Report with counts and samples
        """
        report: Dict[str, Any] = {
            "total": 0,
            "promotable": 0,
            "rejected": 0,
            "by_reason": {},
            "samples": {"promotable": [], "rejected": []},
        }

        try:
            collections = self.old_client.list_collections()

            for coll in collections:
                results = coll.get(include=["documents", "metadatas"])

                documents = results.get("documents") or []
                metadatas = results.get("metadatas") or []

                for i, doc in enumerate(documents):
                    report["total"] += 1

                    metadata = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
                    importance = float(metadata.get("importance", None) or 0.3)  # type: ignore[arg-type]
                    repetitions = int(metadata.get("repetition_count", None) or 1)  # type: ignore[arg-type]

                    should_keep, reason = PromotionCriteria.should_promote(
                        content=doc or "",
                        repetitions=repetitions,
                        importance=importance,
                    )

                    if should_keep:
                        report["promotable"] += 1
                        if len(report["samples"]["promotable"]) < 5:
                            report["samples"]["promotable"].append(
                                {"content": doc[:100], "reason": reason}
                            )
                    else:
                        report["rejected"] += 1
                        if len(report["samples"]["rejected"]) < 5:
                            report["samples"]["rejected"].append(
                                {"content": doc[:100], "reason": reason}
                            )

                    report["by_reason"][reason] = report["by_reason"].get(reason, 0) + 1

        except Exception as e:
            _log.error("Migration analysis error", error=str(e))

        return report

    def migrate(self, dry_run: bool = True) -> Dict[str, Any]:
        """Run migration.

        Args:
            dry_run: If True, only analyze without migrating

        Returns:
            Migration report
        """
        if not self.new_long_term and not dry_run:
            raise ValueError("new_long_term required for actual migration")

        # PERF-039: Reuse data from analyze to avoid double fetch
        report: Dict[str, Any] = {"total": 0, "promotable": 0, "rejected": 0, "by_reason": {}, "samples": {"promotable": [], "rejected": []}}
        migrated = 0

        try:
            collections = self.old_client.list_collections()

            for coll in collections:
                results = coll.get(include=["documents", "metadatas"])

                documents = results.get("documents") or []
                metadatas = results.get("metadatas") or []

                for i, doc in enumerate(documents):
                    report["total"] += 1
                    metadata = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
                    importance = float(metadata.get("importance", None) or 0.3)  # type: ignore[arg-type]
                    repetitions = int(metadata.get("repetition_count", None) or 1)  # type: ignore[arg-type]

                    should_keep, reason = PromotionCriteria.should_promote(
                        content=doc or "",
                        repetitions=repetitions,
                        importance=importance,
                    )

                    if should_keep:
                        report["promotable"] += 1
                        if len(report["samples"]["promotable"]) < 5:
                            report["samples"]["promotable"].append({"content": doc[:100], "reason": reason})

                        # Only migrate if not dry_run
                        if not dry_run:
                            mem_type = metadata.get("type", "insight")
                            if mem_type == "conversation":
                                mem_type = "insight"

                            doc_id = self.new_long_term.add(
                                content=doc,
                                memory_type=mem_type,
                                importance=importance,
                                force=True,
                            )

                            if doc_id:
                                migrated += 1
                    else:
                        report["rejected"] += 1
                        if len(report["samples"]["rejected"]) < 5:
                            report["samples"]["rejected"].append({"content": doc[:100], "reason": reason})

                    report["by_reason"][reason] = report["by_reason"].get(reason, 0) + 1

        except Exception as e:
            _log.error("Migration error", error=str(e))

        report["action"] = "dry_run" if dry_run else "migrated"
        if not dry_run:
            report["migrated_count"] = migrated

        return report
