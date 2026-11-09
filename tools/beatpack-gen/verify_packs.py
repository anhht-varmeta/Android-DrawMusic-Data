#!/usr/bin/env python3
"""Checks the bundled Beat Music packs (BEAT-T041, BEAT-T042). Standard library only.

- every file under app/src/main/assets/beatpacks/ is listed in manifest.json with a matching sha256 and a
  source of "generated" or "licensed" (licensed entries must name a "license");
- no manifest entry points at a missing file;
- no pack metadata mentions a third-party source we must not ship (Remixlive/Mixvibes/Wavetick);
- index.json lists >= 6 packs, each pack folder exists and is <= 8 MB.

Exit code 0 = OK, 1 = problems found (printed one per line).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "out/packs"
MANIFEST = Path(__file__).resolve().parent / "manifest.json"
MIN_PACKS = 20
MAX_PACK_BYTES = 8 * 1024 * 1024
FORBIDDEN = ("remixlive", "mixvibes", "wavetick")
SOURCES = {"generated", "licensed"}


def main() -> int:
    problems: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    on_disk = {f.relative_to(ASSETS).as_posix(): f for f in ASSETS.rglob("*") if f.is_file()}

    for rel, f in sorted(on_disk.items()):
        entry = manifest.get(rel)
        if entry is None:
            problems.append(f"not in manifest: {rel}")
            continue
        if entry.get("source") not in SOURCES:
            problems.append(f"unknown source '{entry.get('source')}': {rel}")
        if entry.get("source") == "licensed" and not entry.get("license"):
            problems.append(f"licensed file without license: {rel}")
        if hashlib.sha256(f.read_bytes()).hexdigest() != entry.get("sha256"):
            problems.append(f"sha256 mismatch (file changed outside the generator?): {rel}")
        if f.suffix in (".json", ".drum", ".song"):
            text = f.read_text(encoding="utf-8").lower()
            for word in FORBIDDEN:
                if word in text:
                    problems.append(f"mentions '{word}': {rel}")
    for rel in sorted(set(manifest) - set(on_disk)):
        problems.append(f"manifest entry without file: {rel}")

    packs = json.loads((ASSETS / "index.json").read_text(encoding="utf-8"))["packs"]
    if len(packs) < MIN_PACKS:
        problems.append(f"only {len(packs)} packs, need >= {MIN_PACKS}")
    for pack in packs:
        folder = ASSETS / pack
        if not (folder / "default.json").is_file():
            problems.append(f"pack '{pack}' has no default.json")
            continue
        size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
        if size > MAX_PACK_BYTES:
            problems.append(f"pack '{pack}' is {size / 1e6:.2f} MB > 8 MB")
        print(f"{pack}: {size / 1e6:.2f} MB")

    for p in problems:
        print(p)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
