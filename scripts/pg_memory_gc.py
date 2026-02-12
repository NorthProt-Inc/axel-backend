#!/usr/bin/env python3
"""PostgreSQL Memory Garbage Collection.

8-phase GC for PG-backed memory system:
  Phase 1: Emoji strip (messages, memories)
  Phase 2: LLM summarize (long messages via Gemini)
  Phase 3: Hash dedup (SHA-256 content dedup)
  Phase 4: Decay cleanup (low-importance memories)
  Phase 5: Archive cleanup (old archived_messages)
  Phase 6: Meta cleanup (old memory_access_patterns)
  Phase 7: KG cleanup (stale entities, weak/orphan relations)
  Phase 8: VACUUM ANALYZE
"""

import argparse
import hashlib
import logging
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

if os.path.exists("/app"):
    sys.path.insert(0, "/app")
else:
    sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2

from backend.config import DATABASE_URL, DEFAULT_GEMINI_MODEL

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google.genai").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent

# ── Emoji regex ──────────────────────────────────────────────────────────────

_EMOJI_RE = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map
    "\U0001f1e0-\U0001f1ff"  # flags
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "\U0001fa00-\U0001fa6f"  # chess symbols
    "\U0001fa70-\U0001faff"  # symbols extended-A
    "\U00002702-\U000027b0"  # dingbats
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U0000200d"  # zero width joiner
    "]+",
    flags=re.UNICODE,
)

SUMMARIZE_PROMPT = """이 메시지를 500자 이내로 요약해주세요.
핵심 내용과 맥락을 보존하고, 불필요한 로그/메타정보를 제거하세요.
원문 언어를 유지하세요. 요약만 출력하세요.

원본:
{content}"""

PARALLEL_WORKERS = 10


def remove_emoji(text: str) -> str:
    """Remove emoji characters from text."""
    return _EMOJI_RE.sub("", text)


def _content_hash(content: str) -> str:
    """SHA-256 hash of normalized content for dedup."""
    normalized = content.strip().lower()[:500]
    return hashlib.sha256(normalized.encode()).hexdigest()


# ── KeyRotator ───────────────────────────────────────────────────────────────


class KeyRotator:
    """Gemini API key rotation (thread-safe)."""

    def __init__(self):
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")

        self.keys = [
            os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_API_KEY_1"),
            os.getenv("GEMINI_API_KEY_2"),
        ]
        self.keys = [k for k in self.keys if k]

        if not self.keys:
            raise ValueError("GEMINI_API_KEY가 .env에 없습니다")

        from google import genai

        self.clients = [genai.Client(api_key=k) for k in self.keys]
        self.current_idx = 0
        self.lock = threading.Lock()
        self.call_counts = {i: 0 for i in range(len(self.keys))}
        logger.info(f"API 키 {len(self.keys)}개 로드됨")

    def get_client(self):
        with self.lock:
            client = self.clients[self.current_idx]
            self.call_counts[self.current_idx] += 1
            self.current_idx = (self.current_idx + 1) % len(self.keys)
            return client

    def get_stats(self) -> dict:
        return {f"key_{i}": cnt for i, cnt in self.call_counts.items()}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_dsn() -> str:
    if not DATABASE_URL:
        logger.error("DATABASE_URL이 설정되지 않았습니다")
        sys.exit(1)
    return DATABASE_URL


def _connect(autocommit: bool = False):
    """Create a raw psycopg2 connection."""
    conn = psycopg2.connect(_get_dsn())
    if autocommit:
        conn.autocommit = True
    return conn


# ── Phase implementations ────────────────────────────────────────────────────


def phase1_emoji_strip(conn, dry_run: bool = False) -> dict:
    """Phase 1: Remove emoji from messages.content and memories.content."""
    print("\n[Phase 1] Emoji strip...")

    result = {"messages_updated": 0, "memories_updated": 0}

    with conn.cursor() as cur:
        # messages
        cur.execute(
            "SELECT id, content FROM messages WHERE content ~ %s",
            (_EMOJI_RE.pattern,),
        )
        msg_rows = cur.fetchall()
        print(f"  Messages with emoji: {len(msg_rows)}")

        if msg_rows and not dry_run:
            for row_id, content in msg_rows:
                cleaned = remove_emoji(content)
                if cleaned != content:
                    cur.execute(
                        "UPDATE messages SET content = %s WHERE id = %s",
                        (cleaned, row_id),
                    )
                    result["messages_updated"] += 1
        elif msg_rows and dry_run:
            result["messages_updated"] = len(msg_rows)
            print(f"  [DRY-RUN] Would update {len(msg_rows)} messages")

        # memories
        cur.execute(
            "SELECT uuid, content FROM memories WHERE content ~ %s",
            (_EMOJI_RE.pattern,),
        )
        mem_rows = cur.fetchall()
        print(f"  Memories with emoji: {len(mem_rows)}")

        if mem_rows and not dry_run:
            for row_uuid, content in mem_rows:
                cleaned = remove_emoji(content)
                if cleaned != content:
                    cur.execute(
                        "UPDATE memories SET content = %s WHERE uuid = %s",
                        (cleaned, row_uuid),
                    )
                    result["memories_updated"] += 1
        elif mem_rows and dry_run:
            result["memories_updated"] = len(mem_rows)
            print(f"  [DRY-RUN] Would update {len(mem_rows)} memories")

    if not dry_run:
        conn.commit()
        print(
            f"  Updated: {result['messages_updated']} messages, "
            f"{result['memories_updated']} memories"
        )

    return result


def _summarize_single(msg_id: int, content: str, client, max_retries: int = 2):
    """Summarize a single message with Gemini (for ThreadPoolExecutor)."""
    from google.genai import types

    prompt = SUMMARIZE_PROMPT.format(content=content[:4000])

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=DEFAULT_GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1024,
                    http_options={"timeout": 60000},
                ),
            )
            if response.text:
                cleaned = response.text.strip()
                if len(cleaned) >= 5:
                    return (msg_id, cleaned, "updated")
        except Exception:
            time.sleep((attempt + 1) * 3)

    return (msg_id, None, "error")


def phase2_llm_summarize(conn, dry_run: bool = False) -> dict:
    """Phase 2: Summarize long messages (>2000 chars) via Gemini."""
    print("\n[Phase 2] LLM summarize (long messages)...")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, content FROM messages WHERE length(content) > 2000"
        )
        long_msgs = cur.fetchall()

    print(f"  Messages > 2000 chars: {len(long_msgs)}")

    if not long_msgs:
        return {"candidates": 0, "updated": 0}

    if dry_run:
        print(f"  [DRY-RUN] Would summarize {len(long_msgs)} messages")
        return {"candidates": len(long_msgs), "updated": 0}

    try:
        rotator = KeyRotator()
    except (ImportError, ValueError) as e:
        print(f"  Skipped: {e}")
        return {"candidates": len(long_msgs), "updated": 0, "error": str(e)}

    updated = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {}
        for msg_id, content in long_msgs:
            client = rotator.get_client()
            future = executor.submit(_summarize_single, msg_id, content, client)
            futures[future] = msg_id

        for future in as_completed(futures):
            try:
                msg_id, cleaned, status = future.result()
                if status == "updated" and cleaned:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE messages SET content = %s WHERE id = %s",
                            (cleaned, msg_id),
                        )
                    updated += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

    conn.commit()
    print(f"  Updated: {updated}, Errors: {errors}")
    print(f"  Key usage: {rotator.get_stats()}")
    return {"candidates": len(long_msgs), "updated": updated, "errors": errors}


def phase3_hash_dedup(conn, dry_run: bool = False) -> dict:
    """Phase 3: Remove duplicate memories by SHA-256 content hash."""
    print("\n[Phase 3] Hash dedup...")

    with conn.cursor() as cur:
        cur.execute("SELECT uuid, content, importance FROM memories")
        rows = cur.fetchall()

    print(f"  Total memories: {len(rows)}")

    hash_groups: dict[str, list] = {}
    for uuid_val, content, importance in rows:
        h = _content_hash(content or "")
        hash_groups.setdefault(h, []).append((uuid_val, importance or 0.5))

    to_delete = []
    for h, entries in hash_groups.items():
        if len(entries) > 1:
            entries.sort(key=lambda x: x[1], reverse=True)
            for uuid_val, _ in entries[1:]:
                to_delete.append(uuid_val)

    print(f"  Duplicates found: {len(to_delete)}")

    if to_delete:
        if dry_run:
            print(f"  [DRY-RUN] Would delete {len(to_delete)} duplicates")
        else:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM memories WHERE uuid = ANY(%s)", (to_delete,)
                )
            conn.commit()
            print(f"  Deleted: {len(to_delete)}")

    return {"total": len(rows), "duplicates": len(to_delete)}


def phase4_decay_cleanup(conn, dry_run: bool = False) -> dict:
    """Phase 4: Remove low-importance decayed memories."""
    print("\n[Phase 4] Decay cleanup...")

    condition = """
        (decayed_importance IS NOT NULL AND decayed_importance < 0.1)
        OR (importance < 0.1 AND access_count <= 1)
    """

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM memories WHERE {condition}")
        count = cur.fetchone()[0]

    print(f"  Candidates for deletion: {count}")

    if count == 0:
        return {"deleted": 0}

    if dry_run:
        print(f"  [DRY-RUN] Would delete {count} decayed memories")
        return {"deleted": count}

    with conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM memories WHERE {condition} RETURNING uuid"
        )
        deleted = len(cur.fetchall())
    conn.commit()
    print(f"  Deleted: {deleted}")
    return {"deleted": deleted}


def phase5_archive_cleanup(conn, dry_run: bool = False) -> dict:
    """Phase 5: Remove archived_messages older than 90 days."""
    print("\n[Phase 5] Archive cleanup (>90 days)...")

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM archived_messages "
                "WHERE timestamp::timestamptz < NOW() - INTERVAL '90 days'"
            )
            count = cur.fetchone()[0]
    except Exception:
        conn.rollback()
        print("  Skipped: archived_messages table not found")
        return {"deleted": 0, "skipped": True}

    print(f"  Old archived messages: {count}")

    if count == 0:
        return {"deleted": 0}

    if dry_run:
        print(f"  [DRY-RUN] Would delete {count} archived messages")
        return {"deleted": count}

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM archived_messages "
            "WHERE timestamp::timestamptz < NOW() - INTERVAL '90 days' "
            "RETURNING id"
        )
        deleted = len(cur.fetchall())
    conn.commit()
    print(f"  Deleted: {deleted}")
    return {"deleted": deleted}


def phase6_meta_cleanup(conn, dry_run: bool = False) -> dict:
    """Phase 6: Remove old memory_access_patterns (>30 days)."""
    print("\n[Phase 6] Meta cleanup (access patterns >30 days)...")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM memory_access_patterns "
            "WHERE created_at < NOW() - INTERVAL '30 days'"
        )
        count = cur.fetchone()[0]

    print(f"  Old access patterns: {count}")

    if count == 0:
        return {"deleted": 0}

    if dry_run:
        print(f"  [DRY-RUN] Would delete {count} old patterns")
        return {"deleted": count}

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM memory_access_patterns "
            "WHERE created_at < NOW() - INTERVAL '30 days' "
            "RETURNING id"
        )
        deleted = len(cur.fetchall())
    conn.commit()
    print(f"  Deleted: {deleted}")
    return {"deleted": deleted}


def phase7_kg_cleanup(conn, dry_run: bool = False) -> dict:
    """Phase 7: Knowledge Graph cleanup - stale entities, weak/orphan relations."""
    print("\n[Phase 7] Knowledge Graph cleanup...")

    result = {"entities_deleted": 0, "relations_weak": 0, "relations_orphan": 0}

    with conn.cursor() as cur:
        # Stale entities: mentions < 3 AND older than 30 days
        cur.execute(
            "SELECT COUNT(*) FROM entities "
            "WHERE mentions < 3 AND created_at < NOW() - INTERVAL '30 days'"
        )
        stale_entities = cur.fetchone()[0]
        print(f"  Stale entities (mentions<3, >30d): {stale_entities}")

        if stale_entities > 0:
            if dry_run:
                print(f"  [DRY-RUN] Would delete {stale_entities} entities")
                result["entities_deleted"] = stale_entities
            else:
                # Delete relations referencing stale entities first
                cur.execute(
                    "DELETE FROM relations WHERE source_id IN ("
                    "  SELECT entity_id FROM entities "
                    "  WHERE mentions < 3 AND created_at < NOW() - INTERVAL '30 days'"
                    ") OR target_id IN ("
                    "  SELECT entity_id FROM entities "
                    "  WHERE mentions < 3 AND created_at < NOW() - INTERVAL '30 days'"
                    ")"
                )
                cur.execute(
                    "DELETE FROM entities "
                    "WHERE mentions < 3 AND created_at < NOW() - INTERVAL '30 days' "
                    "RETURNING entity_id"
                )
                result["entities_deleted"] = len(cur.fetchall())

        # Weak relations: weight < 0.1
        cur.execute("SELECT COUNT(*) FROM relations WHERE weight < 0.1")
        weak_count = cur.fetchone()[0]
        print(f"  Weak relations (weight<0.1): {weak_count}")

        if weak_count > 0:
            if dry_run:
                print(f"  [DRY-RUN] Would delete {weak_count} weak relations")
                result["relations_weak"] = weak_count
            else:
                cur.execute(
                    "DELETE FROM relations WHERE weight < 0.1 RETURNING source_id"
                )
                result["relations_weak"] = len(cur.fetchall())

        # Orphan relations
        cur.execute(
            "SELECT COUNT(*) FROM relations r "
            "WHERE NOT EXISTS (SELECT 1 FROM entities e WHERE e.entity_id = r.source_id) "
            "OR NOT EXISTS (SELECT 1 FROM entities e WHERE e.entity_id = r.target_id)"
        )
        orphan_count = cur.fetchone()[0]
        print(f"  Orphan relations: {orphan_count}")

        if orphan_count > 0:
            if dry_run:
                print(f"  [DRY-RUN] Would delete {orphan_count} orphan relations")
                result["relations_orphan"] = orphan_count
            else:
                cur.execute(
                    "DELETE FROM relations r "
                    "WHERE NOT EXISTS (SELECT 1 FROM entities e WHERE e.entity_id = r.source_id) "
                    "OR NOT EXISTS (SELECT 1 FROM entities e WHERE e.entity_id = r.target_id) "
                    "RETURNING source_id"
                )
                result["relations_orphan"] = len(cur.fetchall())

    if not dry_run:
        conn.commit()
        print(
            f"  Deleted: {result['entities_deleted']} entities, "
            f"{result['relations_weak']} weak relations, "
            f"{result['relations_orphan']} orphan relations"
        )

    return result


def phase8_vacuum(dry_run: bool = False) -> dict:
    """Phase 8: VACUUM ANALYZE (requires autocommit connection)."""
    print("\n[Phase 8] VACUUM ANALYZE...")

    if dry_run:
        print("  [DRY-RUN] Would run VACUUM ANALYZE")
        return {"status": "skipped"}

    tables = [
        "messages",
        "memories",
        "archived_messages",
        "memory_access_patterns",
        "entities",
        "relations",
    ]

    conn = _connect(autocommit=True)
    try:
        with conn.cursor() as cur:
            for table in tables:
                try:
                    cur.execute(f"VACUUM ANALYZE {table}")
                    print(f"  VACUUM ANALYZE {table} ✓")
                except Exception as e:
                    print(f"  VACUUM ANALYZE {table} failed: {e}")
    finally:
        conn.close()

    return {"status": "done", "tables": len(tables)}


# ── Commands ─────────────────────────────────────────────────────────────────


def cmd_check() -> None:
    """Show row counts for all managed tables."""
    print("=" * 60)
    print("PG MEMORY STATUS CHECK")
    print("=" * 60)

    conn = _connect(autocommit=True)
    try:
        tables = [
            ("messages", "SELECT COUNT(*) FROM messages"),
            ("memories", "SELECT COUNT(*) FROM memories"),
            ("archived_messages", "SELECT COUNT(*) FROM archived_messages"),
            ("sessions", "SELECT COUNT(*) FROM sessions"),
            ("memory_access_patterns", "SELECT COUNT(*) FROM memory_access_patterns"),
            ("entities", "SELECT COUNT(*) FROM entities"),
            ("relations", "SELECT COUNT(*) FROM relations"),
            ("interaction_logs", "SELECT COUNT(*) FROM interaction_logs"),
        ]

        for name, sql in tables:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    count = cur.fetchone()[0]
                print(f"  {name:30s} {count:>8,} rows")
            except Exception:
                print(f"  {name:30s} (not found)")
    finally:
        conn.close()

    print("=" * 60)


def cmd_full(dry_run: bool = False) -> None:
    """Run all 8 GC phases."""
    print("=" * 60)
    mode_str = "[DRY-RUN] " if dry_run else ""
    print(f"{mode_str}PG Memory Garbage Collection")
    print("=" * 60)

    conn = _connect()
    gc_errors: list[dict] = []

    import traceback

    phases = [
        ("Phase 1", lambda: phase1_emoji_strip(conn, dry_run)),
        ("Phase 2", lambda: phase2_llm_summarize(conn, dry_run)),
        ("Phase 3", lambda: phase3_hash_dedup(conn, dry_run)),
        ("Phase 4", lambda: phase4_decay_cleanup(conn, dry_run)),
        ("Phase 5", lambda: phase5_archive_cleanup(conn, dry_run)),
        ("Phase 6", lambda: phase6_meta_cleanup(conn, dry_run)),
        ("Phase 7", lambda: phase7_kg_cleanup(conn, dry_run)),
    ]

    results = {}
    for name, fn in phases:
        try:
            results[name] = fn()
        except Exception as e:
            gc_errors.append({"phase": name, "error": str(e), "tb": traceback.format_exc()})
            print(f"  ERROR in {name}: {e}")

    conn.close()

    # Phase 8 uses its own autocommit connection
    try:
        results["Phase 8"] = phase8_vacuum(dry_run)
    except Exception as e:
        gc_errors.append({"phase": "Phase 8", "error": str(e), "tb": traceback.format_exc()})

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY:")
    for name, r in results.items():
        print(f"  {name}: {r}")
    if gc_errors:
        print(f"\n  ERRORS: {len(gc_errors)}")
        for err in gc_errors:
            print(f"    {err['phase']}: {err['error']}")
    print("=" * 60)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="PostgreSQL Memory GC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/pg_memory_gc.py check           # Status check
  python scripts/pg_memory_gc.py full             # Full GC
  python scripts/pg_memory_gc.py full --dry-run   # Dry-run
""",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("check", help="Show table row counts")

    full_parser = subparsers.add_parser("full", help="Run all 8 GC phases")
    full_parser.add_argument("--dry-run", action="store_true", help="Preview without changes")

    args = parser.parse_args(argv)

    if args.command == "check":
        cmd_check()
    elif args.command == "full":
        cmd_full(dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
