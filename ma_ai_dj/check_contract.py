"""Check the bridge's MA API dependencies against the pinned server source."""

import argparse
import ast
from pathlib import Path


def check(server: Path) -> None:
    """Fail when an imported MA helper or required controller method is missing."""
    root = Path(__file__).parent
    for file in (root / "provider").glob("*.py"):
        for node in ast.walk(ast.parse(file.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("music_assistant."):
                source = server / Path(*node.module.split("."))
                candidates = [source.with_suffix(".py"), source / "__init__.py"]
                if not any(path.is_file() for path in candidates):
                    raise ValueError(f"Unsupported MA import: {node.module}")
    required = {
        "music_assistant/controllers/music/controller.py": {"get_active_provider_instances", "get_item_by_uri"},
        "music_assistant/providers/party/__init__.py": {"get_party_player"},
        "music_assistant/controllers/webserver/helpers/auth_middleware.py": {"get_current_user", "get_current_token", "get_current_client_id"},
        "music_assistant/models/provider.py": {"get_setup_value", "get_config_value"},
    }
    for filename, names in required.items():
        tree = ast.parse((server / filename).read_text())
        found = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        if names - found:
            raise ValueError(f"Missing MA API in {filename}: {names - found}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=Path, required=True)
    check(parser.parse_args().server)
    print("Pinned MA server API contract verified")
