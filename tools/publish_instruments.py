"""Publishes the Draw SoundFont instruments to the jsDelivr CDN through this repo. Standard library + git only.

Input is the output of the app's pipeline (088-AND-Draw-Music: ``tools/soundfont/build_catalog.py``): a folder with
``<bank>_<program>.zip`` archives and a ``catalog.json`` whose archive urls are relative.

jsDelivr refuses a version (tag/commit) whose tree is larger than 50 MB, and the instruments are ~125 MB, so:

* the archives are split into parts of at most ``MAX_PART`` bytes; each part is an orphan commit holding only its zips,
  tagged ``instruments-<version>-part<N>``;
* ``instruments/catalog.json`` on ``main`` gets absolute archive urls ``…@<part sha>/<file>.zip`` and the release is
  tagged ``instruments-<version>`` (the app's Remote Config ``instrument_catalog_url`` points at it).

Usage:
    python3 tools/publish_instruments.py <source folder> 1.0.0 [--dry-run]

Nothing is pushed; push with: git push origin main --tags
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "instruments"
REPO = "anhht-varmeta/Android-DrawMusic-Data"
CDN = f"https://cdn.jsdelivr.net/gh/{REPO}"
MAX_FILE = 20 * 1000 * 1000
MAX_PART = 45 * 1000 * 1000
MAX_TREE = 50 * 1000 * 1000
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
TRAILER = os.environ.get("PUBLISH_TRAILER", "").strip()


def message(subject: str) -> str:
    return f"{subject}\n\n{TRAILER}" if TRAILER else subject


def git(*args: str, input: bytes | None = None) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, input=input, check=True,
                          capture_output=True).stdout.decode().strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def part_commit(tag: str, files: list[Path], dry: bool) -> str:
    """Orphan commit whose tree is exactly [files]."""
    if git("tag", "-l", tag):
        sys.exit(f"tag {tag} already exists: publish a new version")
    if dry:
        return "0" * 40
    lines = []
    for f in files:
        blob = git("hash-object", "-w", str(f))
        lines.append(f"100644 blob {blob}\t{f.name}")
    tree = git("mktree", input=("\n".join(lines) + "\n").encode())
    commit = git("commit-tree", tree, "-m", message(f"<add> {tag}: {len(files)} instruments"))
    git("tag", tag, commit)
    return commit


def main(argv: list[str]) -> int:
    if len(argv) < 2 or not SEMVER.match(argv[1]):
        sys.exit("usage: publish_instruments.py <source folder> <semver> [--dry-run]")
    source, version, dry = Path(argv[0]), argv[1], "--dry-run" in argv
    release_tag = f"instruments-{version}"
    if git("tag", "-l", release_tag):
        sys.exit(f"tag {release_tag} already exists")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        sys.exit("run on branch main")

    catalog = json.loads((source / "catalog.json").read_text(encoding="utf-8"))
    if catalog.get("version") != version:
        sys.exit(f"catalog version {catalog.get('version')} != {version}")
    entries = [e for e in catalog["instruments"] if "archive" in e]

    # Check every archive against the catalog before writing anything.
    for e in entries:
        f = source / e["archive"]["url"]
        if f.stat().st_size != e["archive"]["size"] or sha256(f) != e["archive"]["sha256"]:
            sys.exit(f"{f.name}: size/sha256 differ from catalog.json")
        if f.stat().st_size > MAX_FILE:
            sys.exit(f"{f.name} is over the jsDelivr per-file limit")

    parts: list[list[dict]] = [[]]
    used = 0
    for e in entries:
        size = e["archive"]["size"]
        if parts[-1] and used + size > MAX_PART:
            parts.append([])
            used = 0
        parts[-1].append(e)
        used += size

    for n, part in enumerate(parts, start=1):
        tag = f"{release_tag}-part{n}"
        commit = part_commit(tag, [source / e["archive"]["url"] for e in part], dry)
        for e in part:
            e["archive"]["url"] = f"{CDN}@{commit}/{Path(e['archive']['url']).name}"
        print(f"{tag:28} {len(part):3} files {sum(e['archive']['size'] for e in part) / 1e6:6.1f} MB  {commit[:12]}")

    if dry:
        return 0
    DEST.mkdir(exist_ok=True)
    (DEST / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    license_src = source.parent.parent / ".cache" / "LICENSE.txt"
    if license_src.is_file():
        shutil.copyfile(license_src, DEST / "GeneralUser-GS-LICENSE.txt")

    tracked = sum(f.stat().st_size for f in ROOT.rglob("*") if f.is_file() and ".git" not in f.parts
                  and "out" not in f.relative_to(ROOT).parts[:1] and ".venv" not in f.parts)
    if tracked > MAX_TREE:
        sys.exit(f"main tree would be {tracked / 1e6:.1f} MB > jsDelivr 50 MB limit")
    git("add", "-A")
    git("commit", "-m", message(f"<add> instrument catalog {version}: {len(catalog['instruments'])} instruments, "
                                f"{len(parts)} parts"))
    git("tag", release_tag)
    print(f"\ncatalog: {CDN}@{release_tag}/instruments/catalog.json  (main tree {tracked / 1e6:.1f} MB)")
    print("push: git push origin main --tags")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
