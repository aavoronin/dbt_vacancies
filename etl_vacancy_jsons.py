import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

SOURCE_NAME = "vacancy json files"
MAX_BYTES = 64 * 1024
BATCH_SIZE = 1024

SCAN_FOLDERS = [
    r"C:\Py\ScreenAI\out\LinkedIn\Vacancies",
    r"C:\Py\ScreenAI\out\Jabbz\Vacancies",
    r"C:\Py\ScreenAI\out\Hirify\Vacancies",
]

# DDL mirrors the dbt external_table models so the ETL can run
# standalone even if `dbt run` has not created the schema yet.
DDL_SOURCES = """
CREATE TABLE IF NOT EXISTS stage.sources (
    source_id SERIAL PRIMARY KEY,
    source_name TEXT NOT NULL UNIQUE,
    source_dttn TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""
DDL_LOADS = """
CREATE TABLE IF NOT EXISTS stage.loads (
    load_id SERIAL PRIMARY KEY,
    load_dttm TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_id INT NOT NULL REFERENCES stage.sources (source_id)
)
"""
DDL_VACANCY = """
CREATE TABLE IF NOT EXISTS stage.vacancy_jsons (
    vacancy_json_id SERIAL PRIMARY KEY,
    "json" TEXT,
    file_path TEXT NOT NULL UNIQUE,
    file_created_dttm TIMESTAMPTZ,
    file_updated_dttm TIMESTAMPTZ,
    load_id INT REFERENCES stage.loads (load_id)
)
"""

# Insert new files and update existing ones only when the file
# on disk is newer than the row already stored in the database.
UPSERT_SQL = """
INSERT INTO stage.vacancy_jsons
    ("json", file_path, file_created_dttm,
     file_updated_dttm, load_id)
VALUES %s
ON CONFLICT (file_path) DO UPDATE SET
    "json" = EXCLUDED."json",
    file_created_dttm = EXCLUDED.file_created_dttm,
    file_updated_dttm = EXCLUDED.file_updated_dttm,
    load_id = EXCLUDED.load_id
WHERE stage.vacancy_jsons.file_updated_dttm
      < EXCLUDED.file_updated_dttm
RETURNING xmax
"""


def get_password():
    pw = os.environ.get("DBT_PG_PASSWORD")
    if pw:
        return pw
    pw_file = Path(__file__).parent / "dbt_vacancies" / "password.txt"
    if pw_file.exists():
        return pw_file.read_text(encoding="utf-8").strip()
    raise SystemExit("No DBT_PG_PASSWORD env var and no password.txt")


def connect():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        dbname="vacancies",
        password=get_password(),
    )


def ensure_tables(conn):
    with conn, conn.cursor() as cur:
        cur.execute(DDL_SOURCES)
        cur.execute(DDL_LOADS)
        cur.execute(DDL_VACANCY)


def get_source_id(conn):
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO stage.sources (source_name) "
            "VALUES (%s) ON CONFLICT (source_name) "
            "DO NOTHING RETURNING source_id",
            (SOURCE_NAME,),
        )
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "SELECT source_id FROM stage.sources "
            "WHERE source_name = %s",
            (SOURCE_NAME,),
        )
        return cur.fetchone()[0]


def to_utc(ts):
    # File stat times are seconds since the epoch; label them UTC
    # so they map correctly onto a timestamptz column.
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def read_json(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"Skipping unreadable file {path}: {exc}")
        return None


def collect_candidates(conn):
    existing = {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT file_path, file_updated_dttm "
            "FROM stage.vacancy_jsons"
        )
        for fp, upd in cur.fetchall():
            existing[fp] = upd

    candidates = []
    for folder in SCAN_FOLDERS:
        root = Path(folder)
        if not root.is_dir():
            print(f"Folder not found, skipping: {folder}")
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_size >= MAX_BYTES:
                continue
            created = to_utc(stat.st_ctime)
            updated = to_utc(stat.st_mtime)
            key = str(path)
            prev = existing.get(key)
            if prev is not None and prev >= updated:
                continue
            content = read_json(path)
            if content is None:
                continue
            candidates.append((content, key, created, updated))
    return candidates


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def load_batch(conn, source_id, batch):
    # load_dttm is captured at the beginning of the batch.
    batch_ts = datetime.now(timezone.utc)
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO stage.loads (load_dttm, source_id) "
            "VALUES (%s, %s) RETURNING load_id",
            (batch_ts, source_id),
        )
        load_id = cur.fetchone()[0]
        rows = [(c, fp, fc, fu, load_id) for (c, fp, fc, fu) in batch]
        results = execute_values(
            cur, UPSERT_SQL, rows, page_size=BATCH_SIZE, fetch=True
        )
        inserted = sum(1 for r in results if r[0] == 0)
        updated = len(results) - inserted
        unchanged = len(rows) - len(results)
        print(
            f"Processed batch with load_id={load_id} "
            f"inserted={inserted} updated={updated} "
            f"unchanged={unchanged}"
        )
        return inserted, updated, unchanged


def main():
    conn = connect()
    try:
        ensure_tables(conn)
        source_id = get_source_id(conn)
        candidates = collect_candidates(conn)
        print(f"Files to load/update: {len(candidates)}")
        total_inserted = 0
        total_updated = 0
        total_unchanged = 0
        for batch in chunked(candidates, BATCH_SIZE):
            ins, upd, unc = load_batch(conn, source_id, batch)
            total_inserted += ins
            total_updated += upd
            total_unchanged += unc
        print(
            f"Total inserted={total_inserted} "
            f"updated={total_updated} "
            f"unchanged={total_unchanged}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()