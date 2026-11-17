import os
import subprocess
import sys
from pathlib import Path

from project_to_file import project_to_file_main


def run_step(cmd, cwd=None):
    """Execute a command and abort the pipeline if it fails."""
    print(f"Executing: {' '.join(cmd)}")
    print("-" * 40)
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"Step failed with return code {result.returncode}. Aborting.")
        sys.exit(result.returncode)
    print("-" * 40)


def main():
    project_to_file_main()
    # The dbt project is located in the dbt_vacancies subdirectory
    script_dir = Path(__file__).parent
    dbt_project_root = script_dir / "dbt_vacancies"
    password_file = dbt_project_root / "password.txt"

    if not password_file.exists():
        print("Error: password.txt not found!")
        sys.exit(1)

    # Read password safely
    password = password_file.read_text(encoding="utf-8").strip()
    os.environ["DBT_PG_PASSWORD"] = password

    # 1) Run dbt
    # Default to 'run' if no arguments are passed
    dbt_args = sys.argv[1:] if len(sys.argv) > 1 else ["run"]
    dbt_cmd = ["dbt"] + dbt_args
    run_step(dbt_cmd, cwd=dbt_project_root)

    # 2) Run etl_vacancy_jsons.py
    etl_jsons_cmd = [
        sys.executable,
        str(script_dir / "etl" / "etl_vacancy_jsons.py")
    ]
    run_step(etl_jsons_cmd, cwd=script_dir)

    # 3) Run etl_fact_vacancy.py
    etl_fact_cmd = [
        sys.executable,
        str(script_dir / "etl" / "etl_fact_vacancy.py")
    ]
    run_step(etl_fact_cmd, cwd=script_dir)

    print("All pipeline steps completed successfully.")


if __name__ == "__main__":
    main()