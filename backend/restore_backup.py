"""
Restore a Bona School JSON backup into any database — the migration path from
Render Postgres to a locally hosted database.

Steps to move the system in-house:
  1. As the system admin, download the latest backup from Admin → Data Backups
     (or GET /api/admin/backups/<file>).
  2. Point DATABASE_URL at the local database (PostgreSQL or SQLite) and run:

         DATABASE_URL=postgresql://user:pass@localhost/bona_local \
             python restore_backup.py bns_backup_20260709T120000Z.json --wipe

     --wipe clears existing rows first (use it for a clean, exact copy).
  3. Start the backend against the same DATABASE_URL. Done.

The restore inserts tables in foreign-key order and, on PostgreSQL, advances
each table's id sequence past the restored rows so future inserts don't clash.
"""
import json
import sys
from datetime import datetime, date

from sqlalchemy import text

from database import engine, Base
import models  # noqa: F401 — registers all tables on Base


def _coerce(column, value):
    """Convert JSON-safe values back to the column's Python type."""
    if value is None:
        return None
    try:
        py_type = column.type.python_type
    except NotImplementedError:
        return value
    if py_type is datetime and isinstance(value, str):
        return datetime.fromisoformat(value)
    if py_type is date and isinstance(value, str):
        return date.fromisoformat(value)
    if py_type is bool and isinstance(value, int):
        return bool(value)
    return value


def main() -> None:
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    wipe = "--wipe" in sys.argv
    if not files:
        print(__doc__)
        sys.exit(1)

    with open(files[0], encoding="utf-8") as f:
        snapshot = json.load(f)
    tables_data = snapshot.get("tables", {})
    print(f"Backup from {snapshot.get('created_at', 'unknown time')} "
          f"({sum(len(v) for v in tables_data.values())} rows total)")

    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        if wipe:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
            print("Existing rows cleared.")

        for table in Base.metadata.sorted_tables:
            rows = tables_data.get(table.name, [])
            if not rows:
                continue
            payload = [
                {k: _coerce(table.c[k], v) for k, v in row.items() if k in table.c}
                for row in rows
            ]
            conn.execute(table.insert(), payload)
            print(f"  {table.name:<22} {len(rows):>6} rows")

        # PostgreSQL: advance id sequences past the restored rows
        if engine.dialect.name == "postgresql":
            for table in Base.metadata.sorted_tables:
                if "id" in table.c:
                    conn.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM \"{table.name}\"), 1))"
                    ))
            print("PostgreSQL id sequences advanced.")

    print("\nRestore complete — start the backend against this DATABASE_URL.")


if __name__ == "__main__":
    main()
