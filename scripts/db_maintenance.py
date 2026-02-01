#!/usr/bin/env python3

import sqlite3
import logging
import sys
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "sqlite_memory.db"

def get_db_stats(conn: sqlite3.Connection) -> dict:

    cursor = conn.cursor()

    cursor.execute("PRAGMA page_count")
    page_count = cursor.fetchone()[0]

    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]

    cursor.execute("PRAGMA freelist_count")
    freelist_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sessions")
    session_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages")
    message_count = cursor.fetchone()[0]

    try:
        cursor.execute("SELECT COUNT(*) FROM interaction_logs")
        log_count = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        log_count = 0

    return {
        "db_size_mb": round(page_count * page_size / (1024 * 1024), 2),
        "page_count": page_count,
        "freelist_pages": freelist_count,
        "wasted_space_mb": round(freelist_count * page_size / (1024 * 1024), 2),
        "sessions": session_count,
        "messages": message_count,
        "interaction_logs": log_count,
    }

def run_maintenance(db_path: Path = DB_PATH, dry_run: bool = False) -> dict:

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return {"error": "Database not found", "path": str(db_path)}

    logger.info(f"Starting maintenance on {db_path}")
    start_time = datetime.now()

    results = {
        "db_path": str(db_path),
        "started_at": start_time.isoformat(),
        "dry_run": dry_run,
    }

    conn = sqlite3.connect(db_path, timeout=30.0)

    try:

        stats_before = get_db_stats(conn)
        results["before"] = stats_before
        logger.info(f"Before: {stats_before['db_size_mb']}MB, "
                   f"{stats_before['freelist_pages']} free pages, "
                   f"{stats_before['messages']} messages")

        if dry_run:
            logger.info("Dry run mode - skipping maintenance operations")
            results["status"] = "dry_run"
            return results

        cursor = conn.cursor()

        logger.info("Running WAL checkpoint...")
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        wal_result = cursor.fetchone()
        results["wal_checkpoint"] = {
            "status": "ok" if wal_result[0] == 0 else "busy",
            "pages_written": wal_result[1],
            "pages_moved": wal_result[2],
        }
        logger.info(f"WAL checkpoint: {results['wal_checkpoint']}")

        logger.info("Running VACUUM (this may take a while)...")
        cursor.execute("VACUUM")
        logger.info("VACUUM complete")

        logger.info("Running ANALYZE...")
        cursor.execute("ANALYZE")
        logger.info("ANALYZE complete")

        logger.info("Running integrity check...")
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        results["integrity_check"] = integrity_result

        if integrity_result != "ok":
            logger.error(f"Integrity check FAILED: {integrity_result}")
        else:
            logger.info("Integrity check passed")

        stats_after = get_db_stats(conn)
        results["after"] = stats_after

        space_saved = stats_before["db_size_mb"] - stats_after["db_size_mb"]
        results["space_saved_mb"] = round(space_saved, 2)

        logger.info(f"After: {stats_after['db_size_mb']}MB, "
                   f"{stats_after['freelist_pages']} free pages")

        if space_saved > 0:
            logger.info(f"Space saved: {space_saved:.2f}MB")

        results["status"] = "success"

    except Exception as e:
        logger.error(f"Maintenance failed: {e}")
        results["status"] = "error"
        results["error"] = str(e)

    finally:
        conn.close()
        elapsed = (datetime.now() - start_time).total_seconds()
        results["elapsed_seconds"] = round(elapsed, 1)
        logger.info(f"Maintenance completed in {elapsed:.1f}s")

    return results

def main():

    import argparse

    parser = argparse.ArgumentParser(
        description="Run SQLite database maintenance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/db_maintenance.py              # Run maintenance
  python scripts/db_maintenance.py --dry-run    # Show stats only
  python scripts/db_maintenance.py --json       # Output as JSON
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show database stats without running maintenance"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help=f"Path to database (default: {DB_PATH})"
    )

    args = parser.parse_args()

    results = run_maintenance(db_path=args.db, dry_run=args.dry_run)

    if args.json:
        import json
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:

        if results.get("status") == "success":
            print(f"\n DB Maintenance Complete")
            print(f"   Before: {results['before']['db_size_mb']}MB")
            print(f"   After:  {results['after']['db_size_mb']}MB")
            if results.get("space_saved_mb", 0) > 0:
                print(f"   Saved:  {results['space_saved_mb']}MB")
            print(f"   Integrity: {results['integrity_check']}")
            print(f"   Time: {results['elapsed_seconds']}s")
        elif results.get("status") == "dry_run":
            print(f"\n DB Stats (dry run)")
            print(f"   Size: {results['before']['db_size_mb']}MB")
            print(f"   Sessions: {results['before']['sessions']}")
            print(f"   Messages: {results['before']['messages']}")
            print(f"   Logs: {results['before']['interaction_logs']}")
            print(f"   Wasted: {results['before']['wasted_space_mb']}MB")
        else:
            print(f"\n Maintenance Failed: {results.get('error', 'Unknown error')}")
            sys.exit(1)

if __name__ == "__main__":
    main()
