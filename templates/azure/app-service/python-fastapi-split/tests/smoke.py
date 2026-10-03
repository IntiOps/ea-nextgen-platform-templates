"""Bounded HTTP check; success requires the expected commit, not merely a 200 response."""
import argparse
import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def verify(payload, revision):
    return isinstance(payload, dict) and payload.get("status") == "ok" and payload.get("revision") == revision


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--attempts", type=int, default=30)
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or not 1 <= args.attempts <= 60:
        parser.error("an HTTPS application URL and 1–60 attempts are required")
    for attempt in range(args.attempts):
        try:
            with urllib.request.urlopen(args.url.rstrip("/") + "/health", timeout=10) as response:
                payload = json.loads(response.read(4096))
            if verify(payload, args.revision):
                print(json.dumps({"status": "verified", "revision": args.revision, "url": args.url}))
                return 0
        except (OSError, ValueError, urllib.error.URLError):
            pass
        if attempt + 1 < args.attempts:
            time.sleep(10)
    raise SystemExit("Health check did not verify the expected revision")


if __name__ == "__main__":
    main()
