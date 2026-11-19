import os
import json
from datetime import datetime, timezone
from pathlib import Path
import psycopg2

BATCH_SIZE = 1024
VACANCY_VERSION = 3

SKILL_LEVELS = ["expert", "required", "nice-to-have"]

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


def ensure_skill_levels(conn):
    """Seed the fixed skill_level dimension with the 3 expected levels."""
    with conn, conn.cursor() as cur:
        for idx, name in enumerate(SKILL_LEVELS, start=1):
            cur.execute("""
                INSERT INTO dim.skill_levels (skill_level_id, skill_level_name)
                VALUES (%s, %s) ON CONFLICT (skill_level_id) DO NOTHING
            """, (idx, name))


def ensure_partition(cur, table_name, partition_key):
    """Create partition for the given partition_key if it doesn't exist."""
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


def get_source_id(conn):
    with conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO stage.sources (source_name)
            VALUES ('stage.vacancy_jsons') ON CONFLICT (source_name) DO NOTHING 
            RETURNING source_id
        """)
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "SELECT source_id FROM stage.sources WHERE source_name = 'stage.vacancy_jsons'"
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


def get_skill_level_id(cur, level_name):
    cur.execute(
        "SELECT skill_level_id FROM dim.skill_levels WHERE skill_level_name = %s",
        (level_name,)
    )
    row = cur.fetchone()
    return row[0] if row else None


def get_skill_id(cur, skill_name, load_dttm, load_id, source_id):
    """Get or create a skill. Names are stored lowercase for case-insensitive match."""
    if skill_name is None or str(skill_name).strip() == "":
        return None

    name_lower = str(skill_name).strip().lower()

    cur.execute("SELECT skill_id FROM dim.skills WHERE skill_name = %s", (name_lower,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute("""
        INSERT INTO dim.skills
            (skill_id, skill_name, load_dttm, load_id, source_id)
        VALUES ((SELECT COALESCE(MAX(skill_id), 0) + 1 FROM dim.skills),
                %s, %s, %s, %s) ON CONFLICT (skill_name) DO NOTHING
        RETURNING skill_id
    """, (name_lower, load_dttm, load_id, source_id))

    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute("SELECT skill_id FROM dim.skills WHERE skill_name = %s", (name_lower,))
    return cur.fetchone()[0]


def get_m2m_dim_id(cur, table, id_col, name_col, val, load_dttm, load_id, source_id):
    """Generic helper for many-to-many dimensions (countries, languages, certs)."""
    if val is None or str(val).strip() == "":
        return None

    name_lower = str(val).strip().lower()

    cur.execute(f"SELECT {id_col} FROM dim.{table} WHERE {name_col} = %s", (name_lower,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(f"""
        INSERT INTO dim.{table} ({id_col}, {name_col}, load_dttm, load_id, source_id)
        VALUES ((SELECT COALESCE(MAX({id_col}), 0) + 1 FROM dim.{table}), %s, %s, %s, %s)
        ON CONFLICT ({name_col}) DO NOTHING
        RETURNING {id_col}
    """, (name_lower, load_dttm, load_id, source_id))

    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(f"SELECT {id_col} FROM dim.{table} WHERE {name_col} = %s", (name_lower,))
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
    """
    Extract a field from the preferred estimation (estimation2 if valid, else estimation1).
    For model_id, score, score_percentile: look at top level of estimation object.
    For all other fields: look inside the nested "json" object.
    Returns the field value as a string, or None if missing/invalid.
    """
    model_id_2 = est2.get("model_id") if est2 and isinstance(est2, dict) else None
    model_id_1 = est1.get("model_id") if est1 and isinstance(est1, dict) else None

    use_est2 = model_id_2 is not None and str(model_id_2).lower() not in ("null", "none", "")
    use_est1 = model_id_1 is not None and str(model_id_1).lower() not in ("null", "none", "")

    if not use_est2 and not use_est1:
        return None

    try:
        if field_name in ("model_id", "score", "score_percentile"):
            if use_est2:
                val = est2.get(field_name)
            else:
                val = est1.get(field_name)
        else:
            if use_est2:
                nested_json = est2.get("json") if est2 else None
            else:
                nested_json = est1.get("json") if est1 else None

            if not isinstance(nested_json, dict):
                nested_json = {}

            val = nested_json.get(field_name)

        if val is None:
            return None

        if isinstance(val, (list, tuple)):
            return str(val[0]) if val else None

        if isinstance(val, str):
            return val.strip() if val.strip() else None

        return str(val)
    except Exception as e:
        print(f"Warning: Failed to extract {field_name}: {e}")
        return None


def get_preferred_nested_json(est1, est2, top_level_j):
    """
    Select the nested 'json' object from the preferred estimation based on
    model_id validity, falling back to the top-level JSON if neither is valid.
    """
    model_id_2 = est2.get("model_id") if isinstance(est2, dict) else None
    model_id_1 = est1.get("model_id") if isinstance(est1, dict) else None

    def is_valid(mid):
        return mid is not None and str(mid).lower() not in ("null", "none", "")

    if is_valid(model_id_2):
        nested = est2.get("json")
        if isinstance(nested, dict):
            return nested
    if is_valid(model_id_1):
        nested = est1.get("json")
        if isinstance(nested, dict):
            return nested

    return top_level_j if isinstance(top_level_j, dict) else {}


def extract_skills(j, est1, est2):
    """Extract skills from the preferred estimation's nested json."""
    preferred_json = get_preferred_nested_json(est1, est2, j)
    result = {}
    for level in SKILL_LEVELS:
        raw = preferred_json.get(level) or []
        if not isinstance(raw, list):
            raw = []
        result[level] = [
            str(s).strip().lower()
            for s in raw
            if s is not None and str(s).strip()
        ]
    return result


def extract_m2m_lists(j, est1, est2):
    """Extract EmployerCountry, RequiredLanguages, CertificationsRequired."""
    preferred_json = get_preferred_nested_json(est1, est2, j)

    countries_raw = preferred_json.get("EmployerCountry") or []
    languages_raw = preferred_json.get("RequiredLanguages") or []
    certs_raw = preferred_json.get("CertificationsRequired") or []

    countries = [
        str(c).strip().lower()
        for c in countries_raw
        if c and str(c).strip()
    ]
    languages = [
        str(l).strip().lower()
        for l in languages_raw
        if l and str(l).strip()
    ]
    certifications = [
        str(c).strip().lower()
        for c in certs_raw
        if c and str(c).strip()
    ]
    return countries, languages, certifications


def get_existing_vacancy(cur, vacancy_json_id):
    """Fetch the existing fact.vacancy row or None."""
    cur.execute("""
        SELECT vacancy_fact_id, partition_key, model_id, title_id, level_id,
               employment_type_id, contract_type_id, company_id, company_industry_id,
               vacancy_site_id, vacancy_id, score, score_percentile, saved_date_id,
               parsed_date_id, file_created_date_id, file_updated_date_id,
               version, modified_timestamp
        FROM fact.vacancy
        WHERE vacancy_json_id = %s
    """, (vacancy_json_id,))
    return cur.fetchone()


def get_existing_m2m(cur, fact_table, vacancy_fact_id, partition_key, dim_id_col):
    cur.execute(f"""
        SELECT {dim_id_col}
        FROM fact.{fact_table}
        WHERE vacancy_fact_id = %s AND partition_key = %s
    """, (vacancy_fact_id, partition_key))
    return set(r[0] for r in cur.fetchall())


def apply_m2m_changes(cur, fact_table, vacancy_fact_id, partition_key,
                      new_ids, batch_ts, load_id, source_id, dim_id_col):
    existing = get_existing_m2m(cur, fact_table, vacancy_fact_id, partition_key, dim_id_col)
    to_insert = new_ids - existing
    to_delete = existing - new_ids

    for dim_id in to_delete:
        cur.execute(f"""
            DELETE FROM fact.{fact_table}
            WHERE vacancy_fact_id = %s AND {dim_id_col} = %s AND partition_key = %s
        """, (vacancy_fact_id, dim_id, partition_key))

    for dim_id in to_insert:
        cur.execute(f"""
            INSERT INTO fact.{fact_table}
                (vacancy_fact_id, {dim_id_col}, load_dttm, load_id, source_id, partition_key)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (vacancy_fact_id, dim_id, batch_ts, load_id, source_id, partition_key))

    return bool(to_insert or to_delete)


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main():
    conn = connect()
    try:
        ensure_default_dims(conn)
        ensure_skill_levels(conn)
        source_id = get_source_id(conn)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT vj.vacancy_json_id, vj."json", vj.file_created_dttm, vj.file_updated_dttm
                FROM stage.vacancy_jsons vj
                LEFT JOIN fact.vacancy fv ON vj.vacancy_json_id = fv.vacancy_json_id
                WHERE fv.vacancy_json_id IS NULL
                   OR fv.version IS NULL
                   OR fv.version < %s
                   OR fv.modified_timestamp IS DISTINCT FROM vj.file_updated_dttm
                ORDER BY (vj."json"::json ->> 'saved_date') ASC
            """, (VACANCY_VERSION,))
            rows = cur.fetchall()

        print(f"Total records to process: {len(rows)}")

        total_inserted = 0
        total_updated = 0
        total_unchanged = 0

        for batch in chunked(rows, BATCH_SIZE):
            batch_ts = datetime.now(timezone.utc)
            inserted = 0
            updated = 0
            unchanged = 0

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

                est1 = j.get("estimation1") or {}
                est2 = j.get("estimation2") or {}

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
                    model_id_dim = get_dim_key(cur, "models", "model_id", "model_name", model_id, batch_ts, load_id, source_id)
                    title_id = get_dim_key(cur, "titles", "title_id", "title_name", title, batch_ts, load_id, source_id)
                    level_id = get_dim_key(cur, "levels", "level_id", "level_name", level, batch_ts, load_id, source_id)
                    employment_type_id = get_dim_key(cur, "employment_types", "employment_type_id", "employment_type_name", employment_type, batch_ts, load_id, source_id)
                    contract_type_id = get_dim_key(cur, "contract_types", "contract_type_id", "contract_type_name", contract_type, batch_ts, load_id, source_id)
                    company_id = get_dim_key(cur, "companies", "company_id", "company_name", company_name, batch_ts, load_id, source_id)
                    company_industry_id = get_dim_key(cur, "company_industries", "company_industry_id", "company_industry_name", company_industry, batch_ts, load_id, source_id)
                    vacancy_site_id = get_dim_key(cur, "vacancy_sites", "vacancy_site_id", "vacancy_site_name", vacancy_site, batch_ts, load_id, source_id)
                    vacancy_id_dim = get_dim_key(cur, "vacancy_ids", "vacancy_id", "vacancy_id_name", vacancy_id_str, batch_ts, load_id, source_id)

                    saved_date_str = j.get("saved_date")
                    parsed_date_str = j.get("parsed_date")

                    saved_date_id = get_date_id(saved_date_str)
                    parsed_date_id = get_date_id(parsed_date_str)
                    file_created_date_id = get_date_id(str(file_created_dttm) if file_created_dttm else None)
                    file_updated_date_id = get_date_id(str(file_updated_dttm) if file_updated_dttm else None)
                    partition_key = get_partition_key(saved_date_str)

                    if partition_key == -1:
                        continue

                    ensure_partition(cur, "vacancy", partition_key)
                    ensure_partition(cur, "vacancy_to_skills", partition_key)
                    ensure_partition(cur, "vacancy_to_employer_countries", partition_key)
                    ensure_partition(cur, "vacancy_to_required_languages", partition_key)
                    ensure_partition(cur, "vacancy_to_certifications", partition_key)

                    # Skills
                    new_skills = set()
                    skills_data = extract_skills(j, est1, est2)
                    for level_name, skill_names in skills_data.items():
                        sl_id = get_skill_level_id(cur, level_name)
                        if sl_id is None:
                            continue
                        for s_name in skill_names:
                            s_id = get_skill_id(cur, s_name, batch_ts, load_id, source_id)
                            if s_id is not None:
                                new_skills.add((sl_id, s_id))

                    # M2M Dimensions
                    countries, languages, certifications = extract_m2m_lists(j, est1, est2)

                    new_countries = set()
                    for c in countries:
                        c_id = get_m2m_dim_id(cur, "employer_countries", "country_id", "country_name", c, batch_ts, load_id, source_id)
                        if c_id:
                            new_countries.add(c_id)

                    new_languages = set()
                    for l in languages:
                        l_id = get_m2m_dim_id(cur, "required_languages", "language_id", "language_name", l, batch_ts, load_id, source_id)
                        if l_id:
                            new_languages.add(l_id)

                    new_certifications = set()
                    for cert in certifications:
                        cert_id = get_m2m_dim_id(cur, "certifications", "certification_id", "certification_name", cert, batch_ts, load_id, source_id)
                        if cert_id:
                            new_certifications.add(cert_id)

                    existing = get_existing_vacancy(cur, vacancy_json_id)

                    if existing:
                        (vacancy_fact_id, existing_pk, ex_model, ex_title, ex_level,
                         ex_employment, ex_contract, ex_company, ex_industry, ex_site,
                         ex_vacancy_id, ex_score, ex_percentile, ex_saved, ex_parsed,
                         ex_fcreated, ex_fupdated, ex_version, ex_modified) = existing

                        version_changed = ex_version is None or ex_version != VACANCY_VERSION
                        timestamp_changed = ex_modified != file_updated_dttm

                        fields_changed = (
                            existing_pk != partition_key or ex_model != model_id_dim or
                            ex_title != title_id or ex_level != level_id or
                            ex_employment != employment_type_id or ex_contract != contract_type_id or
                            ex_company != company_id or ex_industry != company_industry_id or
                            ex_site != vacancy_site_id or ex_vacancy_id != vacancy_id_dim or
                            (ex_score is None) != (score is None) or
                            (ex_score is not None and float(ex_score) != float(score)) or
                            (ex_percentile is None) != (score_percentile is None) or
                            (ex_percentile is not None and float(ex_percentile) != float(score_percentile)) or
                            ex_saved != saved_date_id or ex_parsed != parsed_date_id or
                            ex_fcreated != file_created_date_id or ex_fupdated != file_updated_date_id
                        )

                        # Check skills (tuple comparison)
                        cur.execute("""
                            SELECT skill_level_id, skill_id FROM fact.vacancy_to_skills
                            WHERE vacancy_fact_id = %s AND partition_key = %s
                        """, (vacancy_fact_id, existing_pk))
                        existing_skills_tuples = set(tuple(r) for r in cur.fetchall())
                        skills_changed = existing_skills_tuples != new_skills

                        existing_countries = get_existing_m2m(cur, "vacancy_to_employer_countries", vacancy_fact_id, existing_pk, "country_id")
                        countries_changed = existing_countries != new_countries

                        existing_languages = get_existing_m2m(cur, "vacancy_to_required_languages", vacancy_fact_id, existing_pk, "language_id")
                        languages_changed = existing_languages != new_languages

                        existing_certifications = get_existing_m2m(cur, "vacancy_to_certifications", vacancy_fact_id, existing_pk, "certification_id")
                        certifications_changed = existing_certifications != new_certifications

                        if not (version_changed or timestamp_changed or fields_changed or
                                skills_changed or countries_changed or languages_changed or certifications_changed):
                            unchanged += 1
                            continue

                        try:
                            cur.execute("""
                                UPDATE fact.vacancy
                                SET load_dttm = %s, load_id = %s, source_id = %s,
                                    model_id = %s, title_id = %s, level_id = %s,
                                    employment_type_id = %s, contract_type_id = %s,
                                    company_id = %s, company_industry_id = %s,
                                    vacancy_site_id = %s, vacancy_id = %s,
                                    score = %s, score_percentile = %s,
                                    saved_date_id = %s, parsed_date_id = %s,
                                    file_created_date_id = %s, file_updated_date_id = %s,
                                    partition_key = %s, version = %s, modified_timestamp = %s
                                WHERE vacancy_fact_id = %s AND partition_key = %s
                            """, (
                                batch_ts, load_id, source_id, model_id_dim, title_id, level_id,
                                employment_type_id, contract_type_id, company_id, company_industry_id,
                                vacancy_site_id, vacancy_id_dim, score, score_percentile,
                                saved_date_id, parsed_date_id, file_created_date_id, file_updated_date_id,
                                partition_key, VACANCY_VERSION, file_updated_dttm, vacancy_fact_id, existing_pk
                            ))

                            # Apply skill changes (tuple-based)
                            to_insert_skills = new_skills - existing_skills_tuples
                            to_delete_skills = existing_skills_tuples - new_skills
                            for sl_id, s_id in to_delete_skills:
                                cur.execute("""
                                    DELETE FROM fact.vacancy_to_skills
                                    WHERE vacancy_fact_id = %s AND skill_level_id = %s AND skill_id = %s AND partition_key = %s
                                """, (vacancy_fact_id, sl_id, s_id, existing_pk))
                            for sl_id, s_id in to_insert_skills:
                                cur.execute("""
                                    INSERT INTO fact.vacancy_to_skills
                                    (vacancy_fact_id, skill_level_id, skill_id, load_dttm, load_id, source_id, partition_key)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (vacancy_fact_id, sl_id, s_id, batch_ts, load_id, source_id, existing_pk))

                            # Apply M2M changes for other tables
                            apply_m2m_changes(cur, "vacancy_to_employer_countries", vacancy_fact_id, existing_pk, new_countries, batch_ts, load_id, source_id, "country_id")
                            apply_m2m_changes(cur, "vacancy_to_required_languages", vacancy_fact_id, existing_pk, new_languages, batch_ts, load_id, source_id, "language_id")
                            apply_m2m_changes(cur, "vacancy_to_certifications", vacancy_fact_id, existing_pk, new_certifications, batch_ts, load_id, source_id, "certification_id")

                            conn.commit()
                            updated += 1
                        except Exception as e:
                            print(f"ERROR updating vacancy_json_id={vacancy_json_id}: {e}")
                            conn.rollback()
                    else:
                        try:
                            cur.execute("""
                                INSERT INTO fact.vacancy (vacancy_json_id, saved_date_id, parsed_date_id,
                                    file_created_date_id, file_updated_date_id, model_id, title_id, level_id,
                                    employment_type_id, contract_type_id, company_id, company_industry_id,
                                    vacancy_site_id, vacancy_id, score, score_percentile, load_dttm, load_id,
                                    source_id, partition_key, modified_timestamp, version)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING vacancy_fact_id, partition_key
                            """, (
                                vacancy_json_id, saved_date_id, parsed_date_id, file_created_date_id, file_updated_date_id,
                                model_id_dim, title_id, level_id, employment_type_id, contract_type_id, company_id,
                                company_industry_id, vacancy_site_id, vacancy_id_dim, score, score_percentile,
                                batch_ts, load_id, source_id, partition_key, datetime(1900, 1, 1, tzinfo=timezone.utc), 0
                            ))
                            new_vacancy_fact_id, new_pk = cur.fetchone()

                            for sl_id, s_id in new_skills:
                                cur.execute("""
                                    INSERT INTO fact.vacancy_to_skills
                                    (vacancy_fact_id, skill_level_id, skill_id, load_dttm, load_id, source_id, partition_key)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (new_vacancy_fact_id, sl_id, s_id, batch_ts, load_id, source_id, new_pk))

                            for c_id in new_countries:
                                cur.execute("""
                                    INSERT INTO fact.vacancy_to_employer_countries
                                    (vacancy_fact_id, country_id, load_dttm, load_id, source_id, partition_key)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (new_vacancy_fact_id, c_id, batch_ts, load_id, source_id, new_pk))

                            for l_id in new_languages:
                                cur.execute("""
                                    INSERT INTO fact.vacancy_to_required_languages
                                    (vacancy_fact_id, language_id, load_dttm, load_id, source_id, partition_key)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (new_vacancy_fact_id, l_id, batch_ts, load_id, source_id, new_pk))

                            for cert_id in new_certifications:
                                cur.execute("""
                                    INSERT INTO fact.vacancy_to_certifications
                                    (vacancy_fact_id, certification_id, load_dttm, load_id, source_id, partition_key)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (new_vacancy_fact_id, cert_id, batch_ts, load_id, source_id, new_pk))

                            conn.commit()
                            inserted += 1
                        except Exception as e:
                            print(f"ERROR inserting vacancy_json_id={vacancy_json_id}: {e}")
                            conn.rollback()

            total_inserted += inserted
            total_updated += updated
            total_unchanged += unchanged

            print(f"Processed batch with load_id={load_id} inserted={inserted} updated={updated} unchanged={unchanged}")

        print(f"Total inserted={total_inserted} updated={total_updated} unchanged={total_unchanged}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()