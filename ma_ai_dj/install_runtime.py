"""Install the bridge into the exact official MA runtime during image build."""

import importlib.metadata
import json
import shutil
from pathlib import Path

import music_assistant
from music_assistant_frontend import where


def flatten(value: dict, prefix: str) -> dict[str, str]:
    """Convert the provider authoring strings to MA's translation keys."""
    result = {}
    for key, text in value.items():
        name = prefix + "." + key
        if isinstance(text, dict):
            result.update(flatten(text, name))
        elif isinstance(text, str):
            result[name] = text
    return result


def main() -> None:
    """Overlay only the provider, built frontend and new provider translations."""
    refs = json.loads(Path("/tmp/ai-dj-upstream.json").read_text())
    for package, key in (("music-assistant", "server_version"), ("music-assistant-frontend", "frontend_version")):
        if importlib.metadata.version(package) != refs[key]:
            raise ValueError(f"Unsupported {package} runtime")
    root = Path(music_assistant.__file__).parent
    provider = root / "providers/ai_dj"
    if provider.exists():
        raise ValueError("AI DJ provider already installed")
    shutil.copytree("/tmp/ai-dj-provider", provider)
    ui = where()
    shutil.rmtree(ui)
    shutil.copytree("/tmp/ai-dj-frontend", ui)
    english = root / "translations/en.json"
    strings = json.loads(english.read_text())
    strings.update(flatten(json.loads((provider / "strings.json").read_text()), "provider.ai_dj"))
    english.write_text(json.dumps(strings, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
