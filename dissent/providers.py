"""Audited, resumable model calls. No credentials are written to disk."""

import json
import socket
import ssl
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .common import canonical, digest, seed_for, utc_now, validate_response, write_json


@dataclass(frozen=True)
class Config:
    backend: str = "mock"
    model: str = "mock-fixture-v1"
    provider: str = "offline"
    seed: int = 2027
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 8192
    max_tokens_ceiling: int = 32768
    send_seed: bool = False
    dissent_threshold: float = 0.6
    team_size: int = 5
    max_attempts: int = 4
    retry_base_seconds: float = 1.0
    retry_max_seconds: float = 30.0
    request_timeout_seconds: float = 45.0

    def validate(self):
        if self.backend not in {"mock", "openrouter"} or self.team_size != 5:
            raise ValueError("Pilot supports mock/openrouter and exactly five agents")
        for name, low, high in (("temperature", 0, 2), ("top_p", 0.000001, 1), ("dissent_threshold", 0, 1)):
            value = getattr(self, name)
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"Invalid {name}")
        if type(self.seed) is not int or type(self.max_tokens) is not int:
            raise ValueError("seed and max_tokens must be integers")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        for value in (self.retry_base_seconds, self.retry_max_seconds, self.request_timeout_seconds):
            if not math.isfinite(value) or value <= 0 or value > 60:
                raise ValueError("Retry/timeout settings must be finite, positive and at most 60 seconds")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if type(self.max_tokens_ceiling) is not int or self.max_tokens_ceiling < self.max_tokens:
            raise ValueError("max_tokens_ceiling must be an integer at least max_tokens")
        if self.backend == "openrouter":
            if not self.model or self.model == "mock-fixture-v1" or not self.provider or self.provider == "offline":
                raise ValueError("Live runs require an explicit model ID and provider")
            if ":online" in self.model or self.model == "openrouter/auto":
                raise ValueError("Online and automatic model routing are disabled")


def mock_reply(kind, context, task, seed):
    """Synthetic behavior for exercising code, with no access to answer keys."""
    rng = random.Random(seed)
    labels = list(task["options"])
    if kind == "independent":
        answer = rng.choice(labels)
    elif kind in {"debate", "extra_round", "neutral_checkpoint"}:
        answers = [x["answer"] for x in context["peers"]] + [context["own"]["answer"]]
        answer = max(labels, key=answers.count)
    elif kind in {"dissent", "explicit_dissent"}:
        answer = context["original"]["answer"]
    elif kind == "reconsider":
        answer = context["dissent"]["answer"]
    elif kind in {"independent_revision", "reminder_revision"}:
        answer = context["own"]["answer"]
    elif kind == "review_control":
        answer = rng.choice(labels + ["UNRESOLVED"])
    else:
        answer = rng.choice([x["answer"] for x in context["candidates"]] + ["UNRESOLVED"])
    result = {"answer": answer, "reasoning": "Synthetic software-test response; not model evidence.", "confidence": 0.8}
    if kind in {"dissent", "explicit_dissent"}:
        dissent = answer != context["proposal"]
        result.update(stance="DISSENT" if dissent else "AGREE", disputed_claim="The proposed option is unsupported." if dissent else "", evidence="Synthetic alternative justification." if dissent else "")
    return result



class CallFailure(RuntimeError):
    """A recorded terminal call failure; experiment runners may continue other tasks."""


class BudgetExceeded(RuntimeError):
    """Stop the run before dispatching a request over the configured attempt cap."""


class TruncatedResponse(ValueError):
    """Provider explicitly exhausted the output allowance."""


class ProviderFailure(Exception):
    def __init__(self, code, retry_after=None):
        self.code = code
        self.retry_after = retry_after


def retry_after_seconds(value):
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            seconds = (date - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0, seconds) if math.isfinite(seconds) else None


def redact(value, secret):
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]") if secret else value
    if isinstance(value, list):
        return [redact(v, secret) for v in value]
    if isinstance(value, dict):
        return {redact(k, secret): redact(v, secret) for k, v in value.items()}
    return value



def compact_record(record):
    """Keep only scheduling/scoring metadata in memory; full prompts stay on disk."""
    compact = {k: v for k, v in record.items() if k not in {"request", "response"}}
    if "attempts" in compact:
        compact["attempts"] = [{k: v for k, v in attempt.items() if k != "response"} for attempt in compact["attempts"]]
    return compact


class CallStore:
    def __init__(self, directory, config, max_calls=1100, retry_failed=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.config = config
        config.validate()
        self.max_calls = max_calls
        self.retry_failed = retry_failed
        self.before_attempt = lambda: None
        self.records = {}
        for path in self.directory.glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["call_id"] in self.records:
                raise ValueError("Duplicate cached call ID")
            self.records[record["call_id"]] = compact_record(record)
        self._attempt_count = sum(len(r.get("attempts", [r])) for r in self.records.values())
        self.known_cost = sum(a.get("usage", {}).get("cost") for r in self.records.values() for a in r.get("attempts", [r])
                              if isinstance(a.get("usage", {}).get("cost"), (int, float))
                              and math.isfinite(a["usage"]["cost"]))

    @property
    def attempt_count(self):
        return self._attempt_count

    def _save(self, path, record):
        attempts = record["attempts"]
        record["latency_seconds"] = sum(a.get("latency_seconds", 0) for a in attempts)
        for field in ("prompt_tokens", "completion_tokens", "total_tokens", "cost"):
            values = [a.get("usage", {}).get(field) for a in attempts]
            known = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)]
            record["usage"][field] = sum(known) if len(known) == len(values) else None
        write_json(path, record)

    def call(self, call_id, kind, task, context, messages):
        config = self.config
        seed = seed_for(config.seed, call_id)
        payload = {"model": config.model, "messages": messages, "temperature": config.temperature,
                   "top_p": config.top_p, "max_tokens": config.max_tokens, "stream": False,
                   "response_format": {"type": "json_object"}}
        if config.send_seed:
            payload["seed"] = seed
        if config.backend == "openrouter":
            payload["provider"] = {"only": [config.provider], "allow_fallbacks": False, "require_parameters": True}
            payload["plugins"] = []
        request_hash = digest({"config": asdict(config), "payload": payload, "kind": kind})
        record = self.records.get(call_id)
        if record:
            if record["request_sha256"] != request_hash:
                raise ValueError(f"Cached request changed: {call_id}. Use a new run directory.")
            if record["status"] == "ok":
                return validate_response(record["parsed"], kind, task)
            if record["status"] != "paused" and not (self.retry_failed and (record.get("retryable") or record["status"] == "pending")):
                raise CallFailure(f"Recorded failure: {call_id}; transient failures can be resumed with --retry-failed")
            remaining_wait = record.get("retry_not_before", 0) - time.time()
            if remaining_wait > 60:
                raise CallFailure(f"Server cooldown still active: {call_id}; resume later")
            if remaining_wait > 0:
                time.sleep(remaining_wait)
        if self.attempt_count >= self.max_calls:
            raise BudgetExceeded("Request-attempt cap reached; resume with a larger cap")
        key = None
        if config.backend == "openrouter":
            key = os.environ.get("OPENROUTER_API_KEY")
            if not key:
                raise ValueError("Set OPENROUTER_API_KEY before a live run")
        if record is None:
            record = {"call_id": call_id, "kind": kind, "request_sha256": request_hash, "request": payload,
                      "backend": config.backend, "requested_provider": config.provider, "derived_seed": seed,
                      "seed_sent": config.send_seed, "started_at": utc_now(), "status": "pending", "attempts": [],
                      "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None, "cost": None}}
            self.records[call_id] = record
        path = self.directory / (digest(call_id) + ".json")
        if record["attempts"]:
            # Reload the full journal only when extending a failed logical call.
            record = json.loads(path.read_text(encoding="utf-8"))
            self.records[call_id] = record
        effective_max_tokens = record.get("next_max_tokens", config.max_tokens)
        for local_attempt in range(config.max_attempts):
            if self.attempt_count >= self.max_calls:
                record["status"] = "paused"
                self._save(path, record)
                raise BudgetExceeded("Request-attempt cap reached during retries; resume with a larger cap")
            try:
                self.before_attempt()
            except BudgetExceeded:
                if record["attempts"]:
                    record["status"] = "paused"
                    self._save(path, record)
                raise
            attempt = {"number": len(record["attempts"]) + 1, "started_at": utc_now(), "status": "pending",
                       "max_tokens": effective_max_tokens,
                       "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None, "cost": None}}
            record["attempts"].append(attempt)
            self._attempt_count += 1
            record.update(status="pending", retryable=False)
            self._save(path, record)  # Journal before sending; interrupted delivery is ambiguous.
            started = time.perf_counter()
            delay = None
            try:
                if config.backend == "mock":
                    value = mock_reply(kind, context, task, seed)
                    raw = {"model": config.model, "provider": "offline", "choices": [{"message": {"content": canonical(value)}, "finish_reason": "stop"}],
                           "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0}}
                else:
                    attempt_payload = {**payload, "max_tokens": effective_max_tokens}
                    request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=canonical(attempt_payload).encode("utf-8"),
                                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(request, timeout=config.request_timeout_seconds) as response:
                        raw = json.loads(response.read().decode("utf-8"))
                raw = redact(raw, key)
                attempt["response"] = raw
                attempt["usage"] = {k: (raw.get("usage") or {}).get(k) for k in attempt["usage"]}
                if raw.get("error"):
                    code = raw["error"].get("code")
                    try:
                        code = int(code)
                    except (TypeError, ValueError):
                        pass
                    raise ProviderFailure(code)
                record["resolved_model"] = raw.get("model")
                record["resolved_provider"] = raw.get("provider")
                choice = raw["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise TruncatedResponse("Output allowance exhausted")
                if choice.get("finish_reason") != "stop":
                    raise ValueError("Completion truncated, refused, or did not stop normally")
                value = validate_response(json.loads(choice["message"]["content"]), kind, task)
                if kind == "review" and value["answer"] not in {c["answer"] for c in context["candidates"]} | {"UNRESOLVED"}:
                    raise ValueError("Review answer outside candidates")
                record.update(parsed=value, response=raw, status="ok", retryable=False)
                attempt["status"] = "ok"
            except Exception as exc:
                code = None
                if isinstance(exc, urllib.error.HTTPError):
                    code = exc.code
                    delay = retry_after_seconds(exc.headers.get("Retry-After") if exc.headers else None)
                    exc.close()
                elif isinstance(exc, ProviderFailure):
                    code = exc.code
                network = isinstance(exc, (TimeoutError, ConnectionError, socket.timeout)) or (isinstance(exc, urllib.error.URLError) and not isinstance(exc, urllib.error.HTTPError) and not isinstance(exc.reason, ssl.SSLCertVerificationError))
                transient = network or code in {408, 409, 425, 429, 500, 502, 503, 504, 529} or (code == 402 and delay is not None)
                truncated = isinstance(exc, TruncatedResponse)
                if truncated:
                    transient = effective_max_tokens < config.max_tokens_ceiling
                    record["next_max_tokens"] = min(config.max_tokens_ceiling, effective_max_tokens * 2)
                    attempt["finish_reason"] = "length"
                record.update(status="error", error_type=type(exc).__name__, retryable=transient)
                attempt.update(status="error", error_type=type(exc).__name__, retryable=transient, delivery_ambiguous=network)
                if code is not None:
                    attempt["http_status"] = code
                if transient:
                    jitter = random.Random(seed_for(seed, attempt["number"], "retry")).uniform(0, 0.25)
                    delay = max(delay or 0, min(config.retry_max_seconds, config.retry_base_seconds * 2**local_attempt + jitter))
                    record["retry_not_before"] = time.time() + delay
                    attempt["retry_delay_seconds"] = delay
                if truncated and transient:
                    delay = 0.0
                    record["retry_not_before"] = time.time()
                    attempt["retry_delay_seconds"] = delay
                if truncated:
                    print(f"Output truncated for {call_id} at {effective_max_tokens} tokens; "
                          + (f"next allowance {record['next_max_tokens']}." if transient else "configured ceiling reached; response retained for inspection."), flush=True)
            finally:
                reported_cost = attempt.get("usage", {}).get("cost")
                if isinstance(reported_cost, (int, float)) and math.isfinite(reported_cost):
                    self.known_cost += reported_cost
                attempt["latency_seconds"] = time.perf_counter() - started
                attempt["finished_at"] = utc_now()
                record["finished_at"] = utc_now()
                self._save(path, record)
            if record["status"] == "ok":
                self.records[call_id] = compact_record(record)
                return record["parsed"]
            if not record["retryable"] or local_attempt + 1 == config.max_attempts or delay > 60:
                self.records[call_id] = compact_record(record)
                raise CallFailure(f"Call failed: {call_id} ({record['error_type']}); attempts recorded in {path}")
            print(f"Retrying {call_id}: attempt {local_attempt + 2}/{config.max_attempts}, wait {delay:.1f}s", flush=True)
            effective_max_tokens = record.get("next_max_tokens", effective_max_tokens)
            time.sleep(delay)
