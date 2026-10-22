#!/usr/bin/env python
"""Diagnose AI passage generation with one real request.

    read -s HF_TOKEN && export HF_TOKEN && python scripts/check_generation.py \
        --topic "machine learning" --band secondary

Reads HF_TOKEN from the environment. The token is never printed: only whether it is set
and what the Hub says it may do. Makes one request per model until one gives a usable
passage, and prints the model, the raw reply (truncated), the repairs applied, the
validation result and the final outcome or the exact error.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from chorus_api import generate  # noqa: E402


def token_report(token: str) -> None:
    try:
        from huggingface_hub import HfApi, __version__

        print(f"huggingface_hub {__version__}")
        info = HfApi().whoami(token=token)
    except Exception as exc:
        print("whoami failed:", generate.describe_error(exc, token))
        return
    print("user:", info.get("name"), "| type:", info.get("type"), "| plan:", "pro" if info.get("isPro") else "free/other")
    auth = info.get("auth") or {}
    tok = auth.get("accessToken") or {}
    print("token role:", tok.get("role"), "| name:", tok.get("displayName"))
    fg = tok.get("fineGrained")
    if fg:
        scopes = [(s.get("entity", {}).get("type"), s.get("permissions")) for s in fg.get("scoped", [])]
        print("fine grained scopes:", scopes, "| global:", fg.get("global"))
        flat = " ".join(str(x) for x in (fg.get("global") or [])) + " ".join(str(s[1]) for s in scopes)
        if "inference" not in flat:
            print("WARNING: no 'inference.serverless.write' (Make calls to Inference Providers) permission seen.")
    elif tok.get("role") in ("read", "write"):
        print("(a classic read or write token can make inference provider calls)")
    print("orgs:", [o.get("name") for o in info.get("orgs", [])])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topic", default="machine learning")
    ap.add_argument("--band", choices=["elementary", "secondary"], default="secondary")
    ap.add_argument("--model", help="one model id (default: CHORUS_PASSAGE_MODEL or the built in list)")
    ap.add_argument("--show", type=int, default=800, help="characters of raw reply to print")
    args = ap.parse_args()

    token = os.environ.get("HF_TOKEN")
    print("HF_TOKEN set:", bool(token))
    if not token:
        print("RESULT: no_token. The server would fall back to the library.")
        return 2
    token_report(token)

    typed = generate.clean_topic(args.topic)
    print(f"topic: {typed!r} | allowed by blocklist: {bool(typed) and generate.topic_allowed(typed)}")
    if not typed or not generate.topic_allowed(typed):
        print("RESULT: topic_rejected.")
        return 2

    order = [args.model] if args.model else generate.models()
    print("models to try:", order, "| timeout:", generate.TIMEOUT_S, "s")
    code = 1
    for model in order:
        print(f"\n=== {model}")
        try:
            client = generate._make_client(token, model)
            raw = generate._call_model(client, args.band, "science", typed)
        except Exception as exc:
            print("ERROR:", generate.describe_error(exc, token))
            status = generate._status(exc)
            if generate._fatal(exc):
                print("RESULT: model_unavailable (auth or credit). Fix the token or credit; other models will fail the same way.")
                return 1
            print("-> would try the next model")
            continue
        raw = generate.scrub(raw, token, 10**6)
        print(f"raw reply ({len(raw)} chars):", raw[: args.show] + (" ..." if len(raw) > args.show else ""))
        if generate.is_declined(raw):
            print("RESULT: model_declined.")
            return 3
        d = generate.make_draft(raw, args.band, typed)
        print("repairs applied:", d.repairs or "none")
        print("title:", repr(d.title))
        n = len(generate.normalize(d.text))
        print(f"words: {n} (accepted {generate.WORD_RANGE[args.band]})")
        print("validation:", "OK" if not d.problems else d.problems)
        if not d.problems:
            print("\nRESULT: OK, an AI passage would be shown.\n" + d.text)
            return 0
        print("-> would retry / try the next model")
        code = 4
    print("\nRESULT:", "invalid_output (every draft failed the checks)" if code == 4 else "model_unavailable (every model errored)")
    return code


if __name__ == "__main__":
    sys.exit(main())
