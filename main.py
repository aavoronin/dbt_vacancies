import os
import subprocess
import sys
from pathlib import Path

from project_to_file import project_to_file_main


def main():
    project_to_file_main()
    # The dbt project is located in the dbt_vacancies subdirectory
    project_root = Path(__file__).parent / "dbt_vacancies"
    password_file = project_root / "password.txt"

    if not password_file.exists():
        print("Error: password.txt not found!")
        sys.exit(1)

    # Read password safely
    password = password_file.read_text(encoding="utf-8").strip()
    os.environ["DBT_PG_PASSWORD"] = password

    # Default to 'run' if no arguments are passed
    dbt_args = sys.argv[1:] if len(sys.argv) > 1 else ["run"]
    cmd = ["dbt"] + dbt_args

    print(f"Executing: {' '.join(cmd)}")
    print("-" * 40)

    # Run dbt
    process = subprocess.run(cmd, cwd=project_root)
    sys.exit(process.returncode)


if __name__ == "__main__":
    main()