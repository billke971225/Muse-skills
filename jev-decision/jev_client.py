#!/usr/bin/env python3
"""Minimal Jev (TypeSafe System One) decision client.

Reads the API key from a 0600 file (default ~/.config/jev/api_key,
override with JEV_KEY_FILE) and the endpoint from ~/.config/jev/api_url
(override with JEV_API_URL; default https://api.typesafe.ai/v1/systemone).
Never prints the key.

Usage:
    python3 jev_client.py ask --state '<text or json>' \
        --questions '{"q1": {"type": "choice", "instructions": "...", "criteria": {"a": "...", "b": "..."}}}'

    python3 jev_client.py ask --state-file state.txt --questions-file q.json

Prints a single JSON line: {"status": "ok"|"fail_open", ...}.
Fail-open: when there is no key, the API errors, or confidence is
unusable, the caller proceeds with its own judgment.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

API_URL_DEFAULT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_KEY_FILE = os.path.expanduser("~/.config/jev/api_key")
DEFAULT_URL_FILE = os.path.expanduser("~/.config/jev/api_url")
TIMEOUT_S = 10

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-.\s]{7,}\d)(?!\d)")
HEX_RE = re.compile(r"\b(?:[0-9a-fA-F]{32,} |sk-[A-Za-z0-9_-]{8,})\b", re.X)


def redact(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = EMAIL_RE.sub("[email]", text)
    text = PHONE_RE.sub("[phone]", text)
    text = HEX_RE.sub("[token]", text)
    return text


def load_key() -> str | None:
    path = os.environ.get("JEV_KEY_FILE", DEFAULT_KEY_FILE)
    try:
        with open(path) as f:
            key = f.read().strip()
        return key or None
    except OSError:
        return None


def load_api_url() -> str:
    if os.environ.get("JEV_API_URL"):
        return os.environ["JEV_API_URL"]
    try:
        with open(os.environ.get("JEV_URL_FILE", DEFAULT_URL_FILE)) as f:
            url = f.read().strip()
        if url:
            return url
    except OSError:
        pass
    return API_URL_DEFAULT


def ask(state, questions, model="jev-latest"):
    key = load_key()
    if not key:
        return {"status": "fail_open", "reason": "no_key"}
    body = {
        "model": model,
        "state": redact(state) if isinstance(state, str) else state,
        "questions": questions,
    }
    req = urllib.request.Request(
        load_api_url(),
        data=json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"status": "fail_open", "reason": f"http_{e.code}"}
    except Exception as e:  # network / timeout / parse
        return {"status": "fail_open", "reason": f"error_{type(e).__name__}"}
    latency_ms = int((time.time() - t0) * 1000)
    return {
        "status": "ok",
        "model": payload.get("model"),
        "answers": payload.get("answers", {}),
        "usage": payload.get("usage", {}),
        "latency_ms": latency_ms,
    }


def main(argv):
    if len(argv) < 2 or argv[0] != "ask":
        print(json.dumps({"status": "fail_open", "reason": "usage"}))
        return 2
    args = argv[1:]
    state = None
    questions = None
    i = 0
    while i < len(args):
        if args[i] == "--state" and i + 1 < len(args):
            state = args[i + 1]
            i += 2
        elif args[i] == "--state-file" and i + 1 < len(args):
            with open(args[i + 1]) as f:
                state = f.read()
            i += 2
        elif args[i] == "--questions" and i + 1 < len(args):
            questions = json.loads(args[i + 1])
            i += 2
        elif args[i] == "--questions-file" and i + 1 < len(args):
            with open(args[i + 1]) as f:
                questions = json.load(f)
            i += 2
        else:
            i += 1
    if state is None or questions is None:
        print(json.dumps({"status": "fail_open", "reason": "missing_state_or_questions"}))
        return 2
    print(json.dumps(ask(state, questions), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
