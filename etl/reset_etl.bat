@echo off
setlocal

REM Force UTF-8 encoding to prevent UnicodeDecodeError with localized PostgreSQL errors
set PGCLIENTENCODING=UTF8
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo Changing directory to dbt_vacancies...
cd /d "%~dp0..\dbt_vacancies"

echo Running dbt full-refresh on dim, dict, and fact models...
echo This will DROP and CREATE the tables in those schemas.
dbt run --full-refresh --select dim dict fact

if %errorlevel% neq 0 (
    echo.
    echo ERROR: dbt run failed.
    echo.
    echo TIP: If you still see a UnicodeDecodeError, your PostgreSQL is returning
    echo an error in Russian (e.g., "база данных не найдена"). The UTF-8 fix above
    echo should reveal the TRUE error (like wrong password or missing database).
    echo Please check your dbt_vacancies\profiles.yml and password.txt.
    exit /b %errorlevel%
)

echo.
echo SUCCESS: dim, dict, and fact schemas have been recreated.
echo The stage schema remains intact.
echo.

echo Changing directory back to project root...
cd /d "%~dp0.."

echo Starting ETL process...
call .venv\Scripts\python.exe main.py

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS: ETL process completed successfully.
) else (
    echo.
    echo ERROR: ETL process failed.
    exit /b %errorlevel%
)

endlocal