"""Strict file formats and reproducible identifiers."""

import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def seed_for(*parts):
    return int(digest(parts)[:8], 16) % (2**31)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON") from exc
    return rows


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    # Windows scanners can briefly hold the destination open. Preserve the old
    # complete record until atomic replacement succeeds; never truncate it in place.
    for attempt in range(6):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.025 * 2**attempt)


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")


def load_tasks(path):
    rows = read_jsonl(path)
    seen = set()
    for row in rows:
        if set(row) != {"task_id", "family", "question", "options"}:
            raise ValueError("Tasks must contain only task_id, family, question, options; keep gold separately")
        if not all(isinstance(row[k], str) and row[k].strip() for k in ("task_id", "family", "question")):
            raise ValueError("Task identifiers, families and questions must be nonempty strings")
        if row["task_id"] in seen:
            raise ValueError("Duplicate task_id")
        seen.add(row["task_id"])
        options = row["options"]
        if not isinstance(options, dict) or len(options) < 2 or "UNRESOLVED" in options:
            raise ValueError("Need at least two options; UNRESOLVED is reserved")
        if not all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip() for k, v in options.items()):
            raise ValueError("Option labels and text must be nonempty strings")
        if len(set(options.values())) != len(options):
            raise ValueError("Duplicate option texts")
    if not rows:
        raise ValueError("Task file is empty")
    return rows


def validate_response(value, kind, task):
    """No answer guessing, automatic repairs, or gold-based retries."""
    if not isinstance(value, dict):
        raise ValueError("Response must be a JSON object")
    required = {"answer", "reasoning", "confidence"}
    if kind in {"dissent", "explicit_dissent"}:
        required |= {"stance", "disputed_claim", "evidence"}
    if set(value) != required:
        raise ValueError(f"Expected exactly {sorted(required)}")
    allowed = set(task["options"])
    if kind in {"review", "review_control"}:
        allowed.add("UNRESOLVED")
    if not isinstance(value["answer"], str) or value["answer"] not in allowed:
        raise ValueError("Answer is not an allowed option label")
    confidence = value["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("Confidence must be finite and within [0,1]")
    if not isinstance(value["reasoning"], str) or not value["reasoning"].strip():
        raise ValueError("A nonempty brief justification is required")
    if kind in {"dissent", "explicit_dissent"}:
        if value["stance"] not in ("AGREE", "DISSENT"):
            raise ValueError("Invalid stance")
        if not all(isinstance(value[k], str) for k in ("disputed_claim", "evidence")):
            raise ValueError("Dissent fields must be strings")
    return value
