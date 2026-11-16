import os
import json
from datetime import datetime, timezone
from pathlib import Path
import psycopg2

BATCH_SIZE = 1024

DIM_CONFIG = {
    "models": ("model_id", "model_name"),
    "titles": ("title_id", "title_name"),
    "levels": ("level_id", "level_name"),
    "employment_types": ("employment_type_id", "employment_type_name"),
    "contract_types": ("contract_type_id", "contract_type_name"),
    "companies": ("company_id", "company_name"),
    "company_industries": ("company_industry_id", "company_industry_name"),
    "vacancy_sites": ("vacancy_site_id", "vacancy_site_name"),
    "vacancy_ids": ("vacancy_id", "vacancy_id_name"),
}


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


def ensure_default_dims(conn):
    # DML only: ensure default unknown records exist in dimension tables.
    # Table structures are managed by dbt.
    with conn, conn.cursor() as cur:
        for table, (id_col, name_col) in DIM_CONFIG.items():
            cur.execute(f"""
                INSERT INTO dim.{table} ({id_col}, {name_col})
                VALUES (-1, '-')
                ON CONFLICT ({id_col}) DO NOTHING
            """)


def get_source_id(conn):
    with conn, conn.cursor() as cur:
        cur.execute("""
                    INSERT INTO stage.sources (source_name)
                    VALUES ('stage.vacancy_jsons') ON CONFLICT (source_name) DO NOTHING RETURNING source_id
                    """)
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("SELECT source_id FROM stage.sources WHERE source_name = 'stage.vacancy_jsons'")
        return cur.fetchone()[0]


def get_dim_key(cur, table, id_col, name_col, val, load_dttm, load_id, source_id):
    if val is None or str(val).strip() == "":
        val = "-"

    cur.execute(f"SELECT {id_col} FROM dim.{table} WHERE {name_col} = %s", (val,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(f"""
        INSERT INTO dim.{table} ({id_col}, {name_col}, load_dttm, load_id, source_id)
        VALUES ((SELECT COALESCE(MAX({id_col}), 0) + 1 FROM dim.{table}), %s, %s, %s, %s)
        ON CONFLICT ({name_col}) DO NOTHING
        RETURNING {id_col}
    """, (val, load_dttm, load_id, source_id))

    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(f"SELECT {id_col} FROM dim.{table} WHERE {name_col} = %s", (val,))
    return cur.fetchone()[0]


def get_date_id(dt_str):
    if not dt_str:
        return -1
    try:
        dt = datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
        return int(dt.strftime('%Y%m%d'))
    except Exception:
        return -1


def get_partition_key(dt_str):
    if not dt_str:
        return -1
    try:
        dt = datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
        return int(dt.strftime('%Y%m'))
    except Exception:
        return -1


def get_estimation_field(est1, est2, field_name):
    model_id_2 = est2.get("model_id") if est2 else None
    model_id_1 = est1.get("model_id") if est1 else None

    use_est2 = model_id_2 is not None and str(model_id_2).lower() not in ("null", "none", "")
    use_est1 = model_id_1 is not None and str(model_id_1).lower() not in ("null", "none", "")

    if use_est2:
        return est2.get(field_name)
    elif use_est1:
        return est1.get(field_name)
    else:
        return None


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main():
    conn = connect()
    try:
        ensure_default_dims(conn)
        source_id = get_source_id(conn)

        with conn.cursor() as cur:
            cur.execute("""
                        SELECT vacancy_json_id, "json", file_created_dttm, file_updated_dttm
                        FROM stage.vacancy_jsons
                        ORDER BY ("json"::json ->> 'saved_date') ASC
                        """)
            rows = cur.fetchall()

        print(f"Total records to process: {len(rows)}")

        for batch in chunked(rows, BATCH_SIZE):
            batch_ts = datetime.now(timezone.utc)

            with conn, conn.cursor() as cur:
                cur.execute("""
                            INSERT INTO stage.loads (load_dttm, source_id)
                            VALUES (%s, %s) RETURNING load_id
                            """, (batch_ts, source_id))
                load_id = cur.fetchone()[0]

            for row in batch:
                vacancy_json_id = row[0]
                j = json.loads(row[1])
                file_created_dttm = row[2]
                file_updated_dttm = row[3]

                est1 = j.get("estimation1")
                est2 = j.get("estimation2")

                model_id = get_estimation_field(est1, est2, "model_id")
                title = get_estimation_field(est1, est2, "Title")
                level = get_estimation_field(est1, est2, "Level")
                employment_type = get_estimation_field(est1, est2, "EmploymentType")
                contract_type = get_estimation_field(est1, est2, "ContractType")
                company_name = get_estimation_field(est1, est2, "CompanyName")
                company_industry = get_estimation_field(est1, est2, "CompanyIndustry")
                vacancy_site = get_estimation_field(est1, est2, "VacancySite")
                job_id = get_estimation_field(est1, est2, "JobId")

                score = get_estimation_field(est1, est2, "score")
                score_percentile = get_estimation_field(est1, est2, "score_percentile")

                vacancy_id_str = f"{vacancy_site or 'UNKNOWN'}_{job_id or 'UNKNOWN'}"

                with conn, conn.cursor() as cur:
                    model_id_dim = get_dim_key(cur, "models", "model_id", "model_name", model_id, batch_ts, load_id,
                                               source_id)
                    title_id = get_dim_key(cur, "titles", "title_id", "title_name", title, batch_ts, load_id, source_id)
                    level_id = get_dim_key(cur, "levels", "level_id", "level_name", level, batch_ts, load_id, source_id)
                    employment_type_id = get_dim_key(cur, "employment_types", "employment_type_id",
                                                     "employment_type_name", employment_type, batch_ts, load_id,
                                                     source_id)
                    contract_type_id = get_dim_key(cur, "contract_types", "contract_type_id", "contract_type_name",
                                                   contract_type, batch_ts, load_id, source_id)
                    company_id = get_dim_key(cur, "companies", "company_id", "company_name", company_name, batch_ts,
                                             load_id, source_id)
                    company_industry_id = get_dim_key(cur, "company_industries", "company_industry_id",
                                                      "company_industry_name", company_industry, batch_ts, load_id,
                                                      source_id)
                    vacancy_site_id = get_dim_key(cur, "vacancy_sites", "vacancy_site_id", "vacancy_site_name",
                                                  vacancy_site, batch_ts, load_id, source_id)
                    vacancy_id_dim = get_dim_key(cur, "vacancy_ids", "vacancy_id", "vacancy_id_name", vacancy_id_str,
                                                 batch_ts, load_id, source_id)

                    saved_date_str = j.get("saved_date")
                    parsed_date_str = j.get("parsed_date")

                    saved_date_id = get_date_id(saved_date_str)
                    parsed_date_id = get_date_id(parsed_date_str)
                    file_created_date_id = get_date_id(str(file_created_dttm) if file_created_dttm else None)
                    file_updated_date_id = get_date_id(str(file_updated_dttm) if file_updated_dttm else None)
                    partition_key = get_partition_key(saved_date_str)

                    cur.execute("""
                                SELECT 1
                                FROM fact.vacancy
                                WHERE vacancy_json_id = %s
                                  AND score IS NOT DISTINCT
                                FROM %s
                                    AND score_percentile IS NOT DISTINCT
                                FROM %s
                                    AND model_id IS NOT DISTINCT
                                FROM %s
                                    AND title_id IS NOT DISTINCT
                                FROM %s
                                    AND level_id IS NOT DISTINCT
                                FROM %s
                                    AND employment_type_id IS NOT DISTINCT
                                FROM %s
                                    AND contract_type_id IS NOT DISTINCT
                                FROM %s
                                    AND company_id IS NOT DISTINCT
                                FROM %s
                                    AND company_industry_id IS NOT DISTINCT
                                FROM %s
                                    AND vacancy_site_id IS NOT DISTINCT
                                FROM %s
                                    AND vacancy_id IS NOT DISTINCT
                                FROM %s
                                    AND saved_date_id IS NOT DISTINCT
                                FROM %s
                                    AND parsed_date_id IS NOT DISTINCT
                                FROM %s
                                    AND file_created_date_id IS NOT DISTINCT
                                FROM %s
                                    AND file_updated_date_id IS NOT DISTINCT
                                FROM %s
                                """, (
                                    vacancy_json_id, score, score_percentile, model_id_dim, title_id, level_id,
                                    employment_type_id, contract_type_id, company_id, company_industry_id,
                                    vacancy_site_id, vacancy_id_dim, saved_date_id, parsed_date_id,
                                    file_created_date_id, file_updated_date_id
                                ))

                    if cur.fetchone():
                        continue

                    cur.execute("SELECT 1 FROM fact.vacancy WHERE vacancy_json_id = %s", (vacancy_json_id,))
                    if cur.fetchone():
                        cur.execute("""
                                    UPDATE fact.vacancy
                                    SET load_dttm = %s,
                                        load_id   = %s
                                    WHERE vacancy_json_id = %s
                                    """, (batch_ts, load_id, vacancy_json_id))
                    else:
                        cur.execute("""
                                    INSERT INTO fact.vacancy (vacancy_json_id, saved_date_id, parsed_date_id,
                                                              file_created_date_id, file_updated_date_id,
                                                              model_id, title_id, level_id, employment_type_id,
                                                              contract_type_id, company_id, company_industry_id,
                                                              vacancy_site_id, vacancy_id,
                                                              score, score_percentile, load_dttm, load_id, source_id,
                                                              partition_key)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                            %s)
                                    """, (
                                        vacancy_json_id, saved_date_id, parsed_date_id,
                                        file_created_date_id, file_updated_date_id,
                                        model_id_dim, title_id, level_id, employment_type_id,
                                        contract_type_id, company_id, company_industry_id,
                                        vacancy_site_id, vacancy_id_dim,
                                        score, score_percentile, batch_ts, load_id, source_id, partition_key
                                    ))

            print(f"Processed batch with load_id={load_id}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()