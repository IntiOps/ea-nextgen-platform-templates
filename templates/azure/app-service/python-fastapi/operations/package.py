"""Build the same zip for the same commit and application files."""
import argparse
import json
import re
import zipfile
from pathlib import Path


def build(app, destination, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("a full source commit is required")
    files = {name: (app / name).read_bytes() for name in ("main.py", "requirements.txt")}
    files["build-info.json"] = json.dumps({"revision": revision}, sort_keys=True).encode()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            item = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            item.external_attr = 0o100644 << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1] / "app", args.output, args.revision)
