#!/usr/bin/env python3

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import SQLITE_MEMORY_PATH

DB_PATH = SQLITE_MEMORY_PATH
MIGRATIONS_DIR = PROJECT_ROOT / "scripts" / "migrations"

def ensure_migrations_table(conn: sqlite3.Connection) -> None:

    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY,
            filename TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

def get_applied_migrations(conn: sqlite3.Connection) -> list[dict]:

    cursor = conn.execute(
        "SELECT filename, applied_at FROM _migrations ORDER BY applied_at"
    )
    return [{"filename": row[0], "applied_at": row[1]} for row in cursor.fetchall()]

def get_pending_migrations() -> list[Path]:

    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(MIGRATIONS_DIR.glob("*.sql"))

def get_migration_status(conn: sqlite3.Connection) -> dict:

    applied = get_applied_migrations(conn)
    applied_names = {m["filename"] for m in applied}

    all_files = get_pending_migrations()
    pending = [f for f in all_files if f.name not in applied_names]

    return {
        "db_path": str(DB_PATH),
        "migrations_dir": str(MIGRATIONS_DIR),
        "total_files": len(all_files),
        "applied": len(applied),
        "pending": len(pending),
        "pending_files": [f.name for f in pending],
        "last_applied": applied[-1] if applied else None,
    }

def cmd_status(output_json: bool = False) -> int:

    if not DB_PATH.exists():
        if output_json:
            print(json.dumps({"error": "Database not found", "path": str(DB_PATH)}))
        else:
            print(f"Database not found: {DB_PATH}")
            print("Database will be created on first app startup.")
        return 1

    conn = sqlite3.connect(DB_PATH)
    ensure_migrations_table(conn)

    status = get_migration_status(conn)
    conn.close()

    if output_json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print("\n Migration Status")
        print("=" * 50)
        print(f"  Database:    {status['db_path']}")
        print(f"  Migrations:  {status['migrations_dir']}")
        print("-" * 50)
        print(f"  Total:       {status['total_files']}")
        print(f"  Applied:     {status['applied']}")
        print(f"  Pending:     {status['pending']}")

        if status['last_applied']:
            last = status['last_applied']
            print(f"  Last:        {last['filename']} ({last['applied_at']})")

        if status['pending_files']:
            print("\n  Pending migrations:")
            for name in status['pending_files']:
                print(f"    - {name}")

        print("=" * 50)

    return 0

def cmd_list(output_json: bool = False) -> int:

    if not DB_PATH.exists():
        if output_json:
            print(json.dumps({"error": "Database not found"}))
        else:
            print(f"Database not found: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    ensure_migrations_table(conn)

    applied = get_applied_migrations(conn)
    applied_names = {m["filename"] for m in applied}
    all_files = get_pending_migrations()

    conn.close()

    result = {
        "applied": applied,
        "pending": [f.name for f in all_files if f.name not in applied_names],
    }

    if output_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\n Migration List")
        print("=" * 50)

        if applied:
            print("\n  [Applied]")
            for m in applied:
                print(f"    {m['filename']}  ({m['applied_at']})")
        else:
            print("\n  [Applied] None")

        pending = result["pending"]
        if pending:
            print("\n  [Pending]")
            for name in pending:
                print(f"    {name}")
        else:
            print("\n  [Pending] None")

        print("\n" + "=" * 50)

    return 0

def cmd_apply(dry_run: bool = False, output_json: bool = False) -> int:

    if not DB_PATH.exists():
        msg = "Database not found. Will be created on first app startup."
        if output_json:
            print(json.dumps({"error": msg, "path": str(DB_PATH)}))
        else:
            print(msg)
        return 1

    conn = sqlite3.connect(DB_PATH)
    ensure_migrations_table(conn)

    applied_names = {m["filename"] for m in get_applied_migrations(conn)}
    all_files = get_pending_migrations()
    pending = [f for f in all_files if f.name not in applied_names]

    result = {
        "dry_run": dry_run,
        "pending_count": len(pending),
        "applied": [],
        "failed": None,
    }

    if not pending:
        if output_json:
            result["message"] = "No pending migrations"
            print(json.dumps(result, indent=2))
        else:
            print("No pending migrations.")
        conn.close()
        return 0

    prefix = "[DRY RUN] " if dry_run else ""

    if not output_json:
        print(f"\n{prefix}Applying {len(pending)} migration(s)...")
        print("=" * 50)

    for sql_file in pending:
        if not output_json:
            print(f"  {sql_file.name}...", end=" ")

        if dry_run:
            result["applied"].append(sql_file.name)
            if not output_json:
                print("(would apply)")
            continue

        try:
            sql_content = sql_file.read_text(encoding="utf-8")
            conn.executescript(sql_content)
            conn.execute(
                "INSERT INTO _migrations (filename) VALUES (?)",
                (sql_file.name,)
            )
            conn.commit()
            result["applied"].append(sql_file.name)
            if not output_json:
                print("OK")
        except Exception as e:
            conn.rollback()
            result["failed"] = {"file": sql_file.name, "error": str(e)}
            if not output_json:
                print(f"FAILED: {e}")
            break

    conn.close()

    if output_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 50)
        applied_count = len(result["applied"])
        if result["failed"]:
            print(f"  Applied: {applied_count}/{len(pending)} (stopped on error)")
        else:
            print(f"  {prefix}Applied: {applied_count}/{len(pending)}")

    return 1 if result["failed"] else 0

def main():

    parser = argparse.ArgumentParser(
        description="Database Migration Runner - SQLite 마이그레이션 관리",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_migrations.py              # 상태 확인 (default)
  python scripts/run_migrations.py status       # 상태 요약
  python scripts/run_migrations.py list         # 마이그레이션 목록
  python scripts/run_migrations.py apply        # 마이그레이션 적용
  python scripts/run_migrations.py apply --dry-run  # 미리보기
  python scripts/run_migrations.py status --json    # JSON 출력
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    status_parser = subparsers.add_parser("status", help="마이그레이션 상태 요약")
    status_parser.add_argument("--json", action="store_true", help="JSON 출력")

    list_parser = subparsers.add_parser("list", help="마이그레이션 목록")
    list_parser.add_argument("--json", action="store_true", help="JSON 출력")

    apply_parser = subparsers.add_parser("apply", help="마이그레이션 적용")
    apply_parser.add_argument("--dry-run", action="store_true", help="미리보기 (실제 적용 안 함)")
    apply_parser.add_argument("--json", action="store_true", help="JSON 출력")

    args = parser.parse_args()

    if args.command is None:
        sys.exit(cmd_status())
    elif args.command == "status":
        sys.exit(cmd_status(output_json=args.json))
    elif args.command == "list":
        sys.exit(cmd_list(output_json=args.json))
    elif args.command == "apply":
        sys.exit(cmd_apply(dry_run=args.dry_run, output_json=args.json))

if __name__ == "__main__":
    main()
