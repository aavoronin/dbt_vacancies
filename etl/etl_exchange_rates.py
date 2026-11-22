import os
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values

SOURCE_NAME = "exchange rates csv files"
SCAN_FOLDER = r"C:\Py\ScreenAI\out\Summary"
BATCH_SIZE = 1024

DDL_EXCHANGE_RATES = """
CREATE TABLE IF NOT EXISTS stage.exchange_rates_csvs (
    exchange_rate_id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL,
    currency_code TEXT NOT NULL,
    file_created_dttm TIMESTAMPTZ,
    file_updated_dttm TIMESTAMPTZ,
    exchange_date DATE,
    rate_usd NUMERIC,
    rate_eur NUMERIC,
    load_id INT REFERENCES stage.loads (load_id),
    UNIQUE (file_path, currency_code)
)
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
        cur.execute(DDL_EXCHANGE_RATES)


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
            "SELECT source_id FROM stage.sources WHERE source_name = %s",
            (SOURCE_NAME,),
        )
        return cur.fetchone()[0]


def to_utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def main():
    conn = connect()
    try:
        ensure_tables(conn)
        source_id = get_source_id(conn)

        root = Path(SCAN_FOLDER)
        if not root.is_dir():
            print(f"Folder not found, skipping: {SCAN_FOLDER}")
            return

        files = sorted(root.glob("exchange_rates_*.csv"))
        print(f"Files to process: {len(files)}")

        total_inserted = 0
        total_updated = 0
        total_unchanged = 0

        for file_path in files:
            match = re.search(r"exchange_rates_(\d{4}-\d{2}-\d{2})\.csv$", file_path.name)
            if not match:
                continue

            exchange_date_str = match.group(1)
            try:
                stat = file_path.stat()
            except OSError:
                continue

            created = to_utc(stat.st_ctime)
            updated = to_utc(stat.st_mtime)

            rows = []
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        currency = row.get('Currency', '').strip()
                        if not currency:
                            continue
                        rate_usd = row.get('Rate_USD', '').strip()
                        rate_eur = row.get('Rate_EUR', '').strip()
                        rows.append((
                            currency,
                            float(rate_usd) if rate_usd else None,
                            float(rate_eur) if rate_eur else None
                        ))
            except Exception as e:
                print(f"Skipping unreadable file {file_path}: {e}")
                continue

            if not rows:
                continue

            with conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT file_updated_dttm FROM stage.exchange_rates_csvs WHERE file_path = %s LIMIT 1",
                    (str(file_path),)
                )
                existing_updated = cur.fetchone()

                if existing_updated and existing_updated[0] >= updated:
                    total_unchanged += len(rows)
                    continue

                cur.execute("DELETE FROM stage.exchange_rates_csvs WHERE file_path = %s", (str(file_path),))

                batch_ts = datetime.now(timezone.utc)
                cur.execute(
                    "INSERT INTO stage.loads (load_dttm, source_id) VALUES (%s, %s) RETURNING load_id",
                    (batch_ts, source_id)
                )
                load_id = cur.fetchone()[0]

                insert_data = [
                    (str(file_path), r[0], created, updated, exchange_date_str, r[1], r[2], load_id)
                    for r in rows
                ]
                execute_values(
                    cur,
                    """
                    INSERT INTO stage.exchange_rates_csvs
                    (file_path, currency_code, file_created_dttm, file_updated_dttm,
                     exchange_date, rate_usd, rate_eur, load_id)
                    VALUES %s
                    """,
                    insert_data,
                    page_size=BATCH_SIZE
                )
                total_inserted += len(rows)
                print(f"Loaded {len(rows)} rows from {file_path.name}")

        print(f"Total inserted={total_inserted} updated={total_updated} unchanged={total_unchanged}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()