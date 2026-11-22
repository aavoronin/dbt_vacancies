import os
from datetime import datetime, timezone
from pathlib import Path
import psycopg2

BATCH_SIZE = 1024
EXCHANGE_RATE_VERSION = 1


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


def get_source_id(conn):
    with conn, conn.cursor() as cur:
        cur.execute("""
                    INSERT INTO stage.sources (source_name)
                    VALUES ('stage.exchange_rates_csvs') ON CONFLICT (source_name) DO NOTHING 
            RETURNING source_id
                    """)
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "SELECT source_id FROM stage.sources WHERE source_name = 'stage.exchange_rates_csvs'"
        )
        return cur.fetchone()[0]


def get_dim_key(cur, table, id_col, name_col, val, load_dttm, load_id, source_id):
    if val is None or str(val).strip() == "":
        val = "-"
    cur.execute(f"SELECT {id_col} FROM dim.{table} WHERE {name_col} = %s", (val,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(f"""
        INSERT INTO dim.{table} ({name_col}, load_dttm, load_id, source_id)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT ({name_col}) DO NOTHING
        RETURNING {id_col}
    """, (val, load_dttm, load_id, source_id))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(f"SELECT {id_col} FROM dim.{table} WHERE {name_col} = %s", (val,))
    return cur.fetchone()[0]


def get_date_id(dt):
    if not dt:
        return -1
    try:
        return int(dt.strftime('%Y%m%d'))
    except Exception:
        return -1


def get_partition_key(dt):
    if not dt:
        return -1
    try:
        return int(dt.strftime('%Y%m'))
    except Exception:
        return -1


def ensure_partition(cur, table_name, partition_key):
    partition_name = f"{table_name}_p{partition_key}"
    cur.execute("""
                SELECT 1
                FROM pg_class c
                         JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = %s
                  AND n.nspname = 'fact'
                """, (partition_name,))
    if not cur.fetchone():
        year = partition_key // 100
        month = partition_key % 100
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        cur.execute(f"""
            CREATE TABLE fact.{partition_name}
            PARTITION OF fact.{table_name}
            FOR VALUES FROM ({partition_key}) TO ({next_year * 100 + next_month})
        """)


def get_existing_exchange_rate(cur, date_id, currency_id):
    cur.execute("""
                SELECT exchange_rate_fact_id,
                       partition_key,
                       rate_usd,
                       rate_eur,
                       version,
                       modified_timestamp
                FROM fact.exchange_rates
                WHERE date_id = %s
                  AND currency_id = %s
                """, (date_id, currency_id))
    return cur.fetchone()


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main():
    conn = connect()
    try:
        source_id = get_source_id(conn)

        # Fetch records using a temporary cursor to avoid holding locks during processing
        with conn.cursor() as cur_fetch:
            cur_fetch.execute("""
                              SELECT er.exchange_rate_id,
                                     er.file_path,
                                     er.file_updated_dttm,
                                     er.exchange_date,
                                     er.currency_code,
                                     er.rate_usd,
                                     er.rate_eur
                              FROM stage.exchange_rates_csvs er
                                       LEFT JOIN fact.exchange_rates fer
                                                 ON fer.date_id = TO_CHAR(er.exchange_date::DATE, 'YYYYMMDD')::INT
                 AND fer.currency_id = (
                     SELECT currency_id FROM dim.currencies WHERE currency_code = er.currency_code
                 )
                              WHERE fer.exchange_rate_fact_id IS NULL
                                 OR fer.version IS NULL
                                 OR fer.version
                                  < %s
                                 OR fer.modified_timestamp IS DISTINCT
                              FROM er.file_updated_dttm
                              ORDER BY er.exchange_date ASC
                              """, (EXCHANGE_RATE_VERSION,))
            rows = cur_fetch.fetchall()

        print(f"Total records to process: {len(rows)}")

        total_inserted = 0
        total_updated = 0
        total_unchanged = 0

        for batch in chunked(rows, BATCH_SIZE):
            batch_ts = datetime.now(timezone.utc)
            inserted = 0
            updated = 0
            unchanged = 0

            # Use a single cursor for the entire batch processing
            with conn.cursor() as cur:
                cur.execute("""
                            INSERT INTO stage.loads (load_dttm, source_id)
                            VALUES (%s, %s) RETURNING load_id
                            """, (batch_ts, source_id))
                load_id = cur.fetchone()[0]

                for row in batch:
                    ex_id, file_path, file_updated_dttm, exchange_date, currency_code, rate_usd, rate_eur = row

                    date_id = get_date_id(exchange_date)
                    partition_key = get_partition_key(exchange_date)

                    if partition_key == -1:
                        continue

                    ensure_partition(cur, "exchange_rates", partition_key)

                    currency_id = get_dim_key(cur, "currencies", "currency_id", "currency_code", currency_code,
                                              batch_ts,
                                              load_id, source_id)

                    existing = get_existing_exchange_rate(cur, date_id, currency_id)

                    if existing:
                        fact_id, ex_pk, ex_rate_usd, ex_rate_eur, ex_version, ex_modified = existing

                        version_changed = ex_version is None or ex_version != EXCHANGE_RATE_VERSION
                        timestamp_changed = ex_modified != file_updated_dttm
                        fields_changed = (
                                ex_pk != partition_key or
                                (ex_rate_usd is None) != (rate_usd is None) or
                                (ex_rate_usd is not None and float(ex_rate_usd) != float(rate_usd)) or
                                (ex_rate_eur is None) != (rate_eur is None) or
                                (ex_rate_eur is not None and float(ex_rate_eur) != float(rate_eur))
                        )

                        if not (version_changed or timestamp_changed or fields_changed):
                            unchanged += 1
                            continue

                        try:
                            cur.execute("""
                                        UPDATE fact.exchange_rates
                                        SET load_dttm          = %s,
                                            load_id            = %s,
                                            source_id          = %s,
                                            rate_usd           = %s,
                                            rate_eur           = %s,
                                            partition_key      = %s,
                                            version            = %s,
                                            modified_timestamp = %s
                                        WHERE exchange_rate_fact_id = %s
                                          AND partition_key = %s
                                        """, (
                                            batch_ts, load_id, source_id, rate_usd, rate_eur,
                                            partition_key, EXCHANGE_RATE_VERSION, file_updated_dttm,
                                            fact_id, ex_pk
                                        ))
                            updated += 1
                        except Exception as e:
                            print(f"ERROR updating exchange_rate_id={ex_id}: {e}")
                            conn.rollback()
                            # Re-acquire cursor state if needed, but usually better to skip this record or abort batch
                            # For simplicity, we just continue to next item; the failed update won't be committed
                            continue
                    else:
                        try:
                            cur.execute("""
                                        INSERT INTO fact.exchange_rates (date_id, currency_id, rate_usd, rate_eur,
                                                                         load_dttm, load_id, source_id, partition_key,
                                                                         modified_timestamp, version)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                                                %s) RETURNING exchange_rate_fact_id, partition_key
                                        """, (
                                            date_id, currency_id, rate_usd, rate_eur,
                                            batch_ts, load_id, source_id, partition_key,
                                            datetime(1900, 1, 1, tzinfo=timezone.utc), 0
                                        ))
                            inserted += 1
                        except Exception as e:
                            print(f"ERROR inserting exchange_rate_id={ex_id}: {e}")
                            conn.rollback()
                            continue

                # Commit only once per batch after all inserts/updates are queued
                conn.commit()

            total_inserted += inserted
            total_updated += updated
            total_unchanged += unchanged
            print(f"Processed batch with load_id={load_id} inserted={inserted} updated={updated} unchanged={unchanged}")

        print(f"Total inserted={total_inserted} updated={total_updated} unchanged={total_unchanged}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()