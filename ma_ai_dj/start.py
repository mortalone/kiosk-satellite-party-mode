"""Start the replacement MA only after importing an existing, stopped server."""

import json
import os
import shutil
import socket
from pathlib import Path


def import_data(data: Path, source: Path, enabled: bool) -> Path:
    """Copy the existing data atomically without overwriting a configured server."""
    target = data / "ma-data"
    if target.exists():
        if not (target / "settings.json").is_file():
            raise ValueError("Existing ma-data is incomplete; restore the MA backup before starting")
        return target
    if not enabled:
        raise ValueError("Copy the stopped MA data to /share/ma-ai-dj-import, then enable import_existing_data")
    if not (source / "settings.json").is_file() or not (source / "library.db").is_file():
        raise ValueError("Import requires the complete existing MA data: settings.json and library.db")
    settings = json.loads((source / "settings.json").read_text())
    if not isinstance(settings, dict) or not settings:
        raise ValueError("The imported MA settings are empty or invalid")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("MA import must contain regular files, without symbolic links")
    stage = data / ".ma-import-stage"
    if stage.exists():
        shutil.rmtree(stage)
    try:
        shutil.copytree(source, stage, ignore=shutil.ignore_patterns("options.json", ".cache"))
        os.replace(stage, target)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return target


def main() -> None:
    """Refuse a parallel MA instance and retain the imported server identity."""
    for port in (8094, 8095):
        with socket.socket() as probe:
            try:
                probe.bind(("0.0.0.0", port))
            except OSError as error:
                raise SystemExit(f"Port {port} is already in use. Stop the existing MA addon first.") from error
    options = json.loads(Path("/data/options.json").read_text())
    try:
        target = import_data(Path("/data"), Path("/share/ma-ai-dj-import"), options.get("import_existing_data") is True)
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
    (target / "options.json").write_text(json.dumps({
        "log_level": options.get("log_level", "info"),
        "safe_mode": options.get("safe_mode", False),
    }))
    os.execv("/usr/local/bin/entrypoint.sh", [
        "/usr/local/bin/entrypoint.sh", "--data-dir", str(target),
        "--cache-dir", str(target / ".cache"),
    ])


if __name__ == "__main__":
    main()
