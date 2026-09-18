"""Minimal dotenv loading: literal single-line values, never shell evaluation."""

import os
import re
from pathlib import Path

NAMES = ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_PROVIDER")


def load_env(path=".env", environ=None):
    environ = os.environ if environ is None else environ
    path = Path(path)
    if not path.exists():
        return
    parsed = {}
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"Invalid .env syntax at line {number}; contents withheld")
        if value.startswith(("'", '"')):
            quote = value[0]
            end = value.find(quote, 1)
            if end < 0 or (value[end + 1:].strip() and not value[end + 1:].strip().startswith("#")):
                raise ValueError(f"Invalid .env quoting at line {number}; contents withheld")
            value = value[1:end]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        if key in parsed:
            raise ValueError(f"Duplicate .env setting at line {number}; contents withheld")
        parsed[key] = value
    # Parse fully before changing the environment. Existing variables take priority.
    for key, value in parsed.items():
        if key in NAMES:
            environ.setdefault(key, value)


def model_settings(backend, model=None, provider=None):
    if backend == "mock":
        return model or "mock-fixture-v1", provider or "offline"
    return model or os.environ.get("OPENROUTER_MODEL", ""), provider or os.environ.get("OPENROUTER_PROVIDER", "")


def check_environment():
    from .providers import Config

    missing = [name for name in NAMES if not os.environ.get(name, "").strip()]
    if missing:
        raise ValueError("Missing settings: " + ", ".join(missing))
    model, provider = model_settings("openrouter")
    Config(backend="openrouter", model=model, provider=provider).validate()
    return "API key, model and provider are configured. Local validation passed; no network request made."
