"""Fix Korean spacing errors in stored memories.

Usage:
    python scripts/fix_spacing.py              # dry-run (preview)
    python scripts/fix_spacing.py --apply      # apply changes
    python scripts/fix_spacing.py --target wm      # working_memory.json only
    python scripts/fix_spacing.py --target chroma  # ChromaDB only
    python scripts/fix_spacing.py --target sqlite  # SQLite only
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

if os.path.exists("/app"):
    sys.path.insert(0, "/app")
else:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import CHROMADB_PATH, SQLITE_MEMORY_PATH, WORKING_MEMORY_PATH

# Try native C++ module first, fall back to pure Python
try:
    import axnmihn_native as _native

    def fix_spacing(text: str) -> str:
        return _native.text_ops.fix_korean_spacing(text)

    def fix_spacing_batch(texts: list[str]) -> list[str]:
        return _native.text_ops.fix_korean_spacing_batch(texts)

    _ENGINE = "native C++"
except ImportError:
    _native = None

    def _is_korean(ch: str) -> bool:
        cp = ord(ch)
        return (
            (0xAC00 <= cp <= 0xD7AF)
            or (0x1100 <= cp <= 0x11FF)
            or (0x3130 <= cp <= 0x318F)
        )

    def fix_spacing(text: str) -> str:
        """Pure Python fallback for fix_korean_spacing."""
        if not text:
            return text

        # Rule 6: collapse consecutive spaces
        text = re.sub(r" {2,}", " ", text)

        result: list[str] = []
        n = len(text)
        for i, ch in enumerate(text):
            result.append(ch)
            if i + 1 >= n:
                break
            nxt = text[i + 1]
            if nxt == " ":
                continue

            insert = False

            # Rule 1: .!? + Hangul (not ellipsis)
            if ch in ".!?" and _is_korean(nxt):
                is_ellipsis = ch == "." and (
                    (i > 0 and text[i - 1] == ".")
                    or (i + 1 < n and text[i + 1] == ".")
                )
                if not is_ellipsis:
                    insert = True

            # Rule 2: ])} + Hangul
            if ch in "])}" and _is_korean(nxt):
                insert = True

            # Rule 3: Hangul + [({
            if _is_korean(ch) and nxt in "[({":
                insert = True

            # Rule 4: : + Hangul
            if ch == ":" and _is_korean(nxt):
                insert = True

            # Rule 5: * + Hangul
            if ch == "*" and _is_korean(nxt):
                insert = True

            if insert:
                result.append(" ")

        return "".join(result)

    def fix_spacing_batch(texts: list[str]) -> list[str]:
        return [fix_spacing(t) for t in texts]

    _ENGINE = "Python fallback"


def fix_working_memory(apply: bool) -> dict[str, int]:
    """Fix spacing in working_memory.json messages."""
    path = WORKING_MEMORY_PATH
    if not path.exists():
        print(f"  working_memory.json not found: {path}")
        return {"total": 0, "changed": 0}

    with open(path) as f:
        data = json.load(f)

    messages = data.get("messages", [])
    total = len(messages)
    changed = 0
    diffs: list[tuple[str, str]] = []

    for msg in messages:
        content = msg.get("content", "")
        if not content or not isinstance(content, str):
            continue
        fixed = fix_spacing(content)
        if fixed != content:
            changed += 1
            # Show first diff for preview
            if len(diffs) < 10:
                diffs.append((content[:120], fixed[:120]))
            if apply:
                msg["content"] = fixed

    print(f"  Messages: {total} total, {changed} to fix")
    for orig, fixed in diffs:
        print(f"    - \"{orig}\"")
        print(f"    + \"{fixed}\"")
    if changed > 10:
        print(f"    ... and {changed - 10} more")

    if apply and changed > 0:
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  Applied {changed} fixes to {path}")

    return {"total": total, "changed": changed}


def fix_chromadb(apply: bool) -> dict[str, int]:
    """Fix spacing in ChromaDB documents."""
    try:
        import chromadb
    except ImportError:
        print("  chromadb not installed, skipping")
        return {"total": 0, "changed": 0}

    db_path = str(CHROMADB_PATH)
    if not Path(db_path).exists():
        print(f"  ChromaDB path not found: {db_path}")
        return {"total": 0, "changed": 0}

    client = chromadb.PersistentClient(path=db_path)
    try:
        coll = client.get_collection("axnmihn_memory")
    except Exception:
        print("  Collection 'axnmihn_memory' not found")
        return {"total": 0, "changed": 0}

    # Fetch all documents + embeddings (keep existing embeddings to avoid re-embedding)
    results = coll.get(include=["documents", "embeddings"])
    ids = results["ids"]
    docs = results["documents"]
    embeddings = results["embeddings"]
    total = len(docs)

    # Batch fix
    fixed_docs = fix_spacing_batch(docs)

    # Find changed entries
    update_ids: list[str] = []
    update_docs: list[str] = []
    update_embeddings: list[list[float]] = []
    diffs: list[tuple[str, str]] = []

    for i in range(total):
        if fixed_docs[i] != docs[i]:
            update_ids.append(ids[i])
            update_docs.append(fixed_docs[i])
            update_embeddings.append(embeddings[i])
            if len(diffs) < 10:
                diffs.append((docs[i][:120], fixed_docs[i][:120]))

    changed = len(update_ids)
    print(f"  Documents: {total} total, {changed} to fix")
    for orig, fixed in diffs:
        print(f"    - \"{orig}\"")
        print(f"    + \"{fixed}\"")
    if changed > 10:
        print(f"    ... and {changed - 10} more")

    if apply and changed > 0:
        # ChromaDB update in batches (max 5000 per call)
        # Pass existing embeddings to prevent re-embedding with wrong model
        batch_size = 5000
        for start in range(0, changed, batch_size):
            end = min(start + batch_size, changed)
            coll.update(
                ids=update_ids[start:end],
                documents=update_docs[start:end],
                embeddings=update_embeddings[start:end],
            )
        print(f"  Applied {changed} fixes to ChromaDB")

    return {"total": total, "changed": changed}


def _fix_sqlite_table(
    cursor,
    table: str,
    column: str,
    apply: bool,
) -> dict[str, int]:
    """Fix spacing in a single SQLite table/column pair."""
    cursor.execute(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL")
    rows = cursor.fetchall()
    total = len(rows)
    changed = 0
    diffs: list[tuple[str, str]] = []

    for row_id, content in rows:
        if not content:
            continue
        fixed = fix_spacing(content)
        if fixed != content:
            changed += 1
            if len(diffs) < 5:
                diffs.append((content[:120], fixed[:120]))
            if apply:
                cursor.execute(
                    f"UPDATE {table} SET {column} = ? WHERE id = ?",
                    (fixed, row_id),
                )

    print(f"    {table}.{column}: {total} rows, {changed} to fix")
    for orig, fixed in diffs:
        print(f"      - \"{orig}\"")
        print(f"      + \"{fixed}\"")
    if changed > 5:
        print(f"      ... and {changed - 5} more")

    return {"total": total, "changed": changed}


def fix_sqlite(apply: bool) -> dict[str, int]:
    """Fix spacing in SQLite memory database."""
    import sqlite3

    db_path = SQLITE_MEMORY_PATH
    if not db_path.exists():
        print(f"  SQLite DB not found: {db_path}")
        return {"total": 0, "changed": 0}

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    targets = [
        ("messages", "content"),
        ("sessions", "summary"),
        ("archived_messages", "content"),
    ]

    total_all = 0
    changed_all = 0

    for table, column in targets:
        # Check table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cursor.fetchone():
            print(f"    {table}: table not found, skipping")
            continue
        result = _fix_sqlite_table(cursor, table, column, apply)
        total_all += result["total"]
        changed_all += result["changed"]

    if apply and changed_all > 0:
        conn.commit()
        print(f"  Applied {changed_all} fixes to {db_path}")

    conn.close()
    return {"total": total_all, "changed": changed_all}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix Korean spacing errors in stored memories"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply fixes (default: dry-run preview)",
    )
    parser.add_argument(
        "--target",
        choices=["all", "wm", "chroma", "sqlite"],
        default="all",
        help="Target to fix: all, wm, chroma, sqlite",
    )
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== Korean Spacing Fix ({mode}) ===")
    print(f"Engine: {_ENGINE}")
    print()

    results: dict[str, dict[str, int]] = {}

    if args.target in ("all", "wm"):
        print("[working_memory.json]")
        results["wm"] = fix_working_memory(args.apply)
        print()

    if args.target in ("all", "chroma"):
        print("[ChromaDB]")
        results["chroma"] = fix_chromadb(args.apply)
        print()

    if args.target in ("all", "sqlite"):
        print("[SQLite]")
        results["sqlite"] = fix_sqlite(args.apply)
        print()

    # Summary
    total_changed = sum(r["changed"] for r in results.values())
    total_docs = sum(r["total"] for r in results.values())
    print(f"=== Summary: {total_changed}/{total_docs} documents {'fixed' if args.apply else 'would be fixed'} ===")

    if not args.apply and total_changed > 0:
        print("Run with --apply to apply changes.")


if __name__ == "__main__":
    main()
