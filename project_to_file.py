import os
from pathlib import Path
from charset_normalizer import from_path


def detect_and_read_file(file_path: Path) -> str:
    """
    Detect file encoding using charset-normalizer and return content as string.
    Normalizes all line endings to Unix-style (\n) for consistent output.
    """
    try:
        # Use charset-normalizer for automatic encoding detection
        result = from_path(file_path).best()
        if result:
            content = str(result)
            # Normalize line endings: \r\n → \n, \r → \n
            return content.replace('\r\n', '\n').replace('\r', '\n')
    except Exception:
        pass

    # Fallback: try common encodings with explicit newline handling
    for encoding in ['utf-8', 'latin-1', 'cp1252', 'ascii']:
        try:
            with open(file_path, 'r', encoding=encoding, errors='strict', newline='') as f:
                content = f.read()
                return content.replace('\r\n', '\n').replace('\r', '\n')
        except (UnicodeDecodeError, LookupError):
            continue

    # Last resort: read with utf-8 and ignore errors
    with open(file_path, 'r', encoding='utf-8', errors='ignore', newline='') as f:
        content = f.read()
        return content.replace('\r\n', '\n').replace('\r', '\n')


PROMPT = """
INPUT FORMAT:
The input contains concatenated files delimited by:
'=====START path/to/FileName.ext ====='
...code...
'=====END path/to/FileName.ext ====='
These markers are for parsing only and must NEVER appear in the output.

OUTPUT FORMAT:
- Return ONLY modified or newly created files.
- Each file must be in a separate markdown code block with the correct language identifier (e.g., python, sql, yaml).
- Precede each block with the exact relative file path (e.g., ### 📄 models/dim/my_model.sql or ### 📄 etl_script.py).
- Output complete, runnable file contents. No diffs, no partial snippets.
- Omit unchanged files entirely.

CODING STANDARDS:
General:
1. All comments and user-facing strings must be in English.
2. DO NOT translate technical identifiers, tag names, file paths, API keys, or environment variables.
3. Keep lines ≤80 characters where practical, without breaking syntax or readability.
4. Preserve all existing comments verbatim. Do not delete, rephrase, or move them unless they directly contradict the new logic.
5. Apply ONLY the requested changes. Do not refactor, optimize, reformat, or touch unrelated code.
6. Do NOT add "change log", "modified", or "TODO" comments. Comments must only explain logic, behavior, or business rules.
7. Update imports, dependencies, or configuration if required by the changes.
8. If requirements are ambiguous or conflicting, pause and ask for clarification instead of guessing.
9. Do not add or delete empty lines in the places where code was not changed.

Python (.py):
10. Follow PEP 8. Use parameterized queries (e.g., %s for psycopg2) to prevent SQL injection; never use f-strings for SQL values.

SQL & dbt (.sql):
11. Use UPPERCASE for SQL keywords (SELECT, FROM, WHERE) and lowercase for identifiers.
12. Always use dbt ref() and source() macros to reference models/sources. NEVER hardcode schema or table names.
13. Preserve all Jinja logic, macros, and {{ config(...) }} blocks unless explicitly asked to change them.
14. Align columns and use consistent indentation (4 spaces) in SQL queries.

YAML (.yml, .yaml):
15. Maintain consistent 2-space indentation.
16. Preserve all existing description, tests, and meta fields unless explicitly asked to modify them.
"""


def concatenate_project_files(project_path, output_filename='combined_output.txt'):
    root = Path(project_path)
    output_path = root / output_filename

    # Supported file extensions
    IMAGE_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif",
        ".webp", ".ico", ".svg", ".raw", ".heic", ".heif", ".jfif",
        ".pjpeg", ".pjp", ".apng", ".avif"
    }

    DOCUMENT_EXTENSIONS = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".txt", ".rtf", ".odt", ".ods", ".odp",
        #".csv",
        ".xml", ".md", ".html", ".htm", ".epub", ".mobi"
    }

    exclude_dirs = {'weights', '.idea', '__pycache__', '.venv',
                    '.git', 'premsql', "TestCases", "out", "omniparser",
                    "parsed screens", "screens", 'target'}
    exclude_extensions = {'.pyc', '.pyo', '.pyd', '.mhtml',
                          '.cmd', '.ipynb', '.ipynb_checkpoints',
                          '.ipynb_media', '.sh', '.log', '.gpickle',
                          ".safetensors"} | set(IMAGE_EXTENSIONS) | set(DOCUMENT_EXTENSIONS)
    exclude_filenames = {'.env', '.DS_Store', output_filename,
                         ".gitignore", 'run_results.json', "password.txt", ".gitkeep" }
    exclude_specific_paths = {'download/my_token.py', 'README.md', 'combined_output.txt'}

    # Write with newline='' to prevent double-conversion of \n on Windows
    with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
        outfile.write(PROMPT)
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue

            if any(part in exclude_dirs for part in path.parts):
                continue
            if path.suffix in exclude_extensions:
                continue
            if path.name in exclude_filenames:
                continue

            relative_path = path.relative_to(root)
            if relative_path.as_posix() in exclude_specific_paths:
                continue

            outfile.write(f"=====START {relative_path} =====\n")
            try:
                content = detect_and_read_file(path)
                outfile.write(content)
            except Exception as e:
                outfile.write(f"\n[Error reading file: {e}]\n")
            outfile.write(f"\n=====END {relative_path} =====\n")
            print(relative_path)


def project_to_file_main():
    PROJECT_PATH = r"C:\Py\dbt_vacancies"
    concatenate_project_files(PROJECT_PATH)
    print(f"Done: {PROJECT_PATH}\\combined_output.txt")
