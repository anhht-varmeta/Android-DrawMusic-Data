#!/usr/bin/env python3
"""Publishes Beat packs to the jsDelivr CDN through this GitHub repo. Standard library + git only.

jsDelivr serves a GitHub repo per version (tag/commit) and refuses versions whose tree is larger than 50 MB
(single files: 20 MB). All packs together are ~76 MB, so they are split:

* every pack is one zip stored alone in an orphan commit, tagged ``pack-<id>-<version>``;
  the catalog links that commit by its SHA (immutable, cached by jsDelivr "forever");
* ``main`` holds only the light part — ``catalog.json`` + ``packs/<id>/cover.webp`` + ``packs/<id>/preview.ogg`` —
  and every catalog release is a semver tag (``1.1.0``) that Remote Config points at.

Usage (repo root):
    python3 tools/publish.py 1.1.0            # build zips, pack commits/tags, catalog; commit main + tag 1.1.0
    python3 tools/publish.py 1.1.0 --dry-run  # only print what would happen
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
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS_SRC = ROOT / "out/packs"
ZIP_DIR = ROOT / "out/zips"
CATALOG = ROOT / "catalog.json"
CATALOG_ASSETS = ROOT / "packs"
REPO = "anhht-varmeta/Android-DrawMusic-Data"
CDN = f"https://cdn.jsdelivr.net/gh/{REPO}"
SCHEMA = 1
MAX_FILE = 20 * 1000 * 1000
MAX_TREE = 50 * 1000 * 1000
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
# Fixed timestamp so a zip is byte-identical when its files are (same sha256 → no new pack commit).
ZIP_TIME = (2026, 1, 1, 0, 0, 0)
# Optional commit trailer (e.g. "Co-Authored-By: …") appended to every commit message this script makes.
TRAILER = os.environ.get("PUBLISH_TRAILER", "").strip()


def message(subject: str) -> str:
    return f"{subject}\n\n{TRAILER}" if TRAILER else subject


def git(*args: str, input: bytes | None = None) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, input=input, check=True,
                          capture_output=True).stdout.decode().strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_zip(pack_id: str) -> Path:
    """Deterministic zip of out/packs/<id>/ with entries at the root (default.json, 8x6.json, samples/…)."""
    src = PACKS_SRC / pack_id
    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    dest = ZIP_DIR / f"{pack_id}.zip"
    with zipfile.ZipFile(dest, "w") as z:
        for f in sorted(p for p in src.rglob("*") if p.is_file()):
            rel = f.relative_to(src).as_posix()
            info = zipfile.ZipInfo(rel, ZIP_TIME)
            info.external_attr = 0o644 << 16
            # Ogg/webp are already compressed: storing them keeps the zip fast to unpack on phones.
            info.compress_type = zipfile.ZIP_STORED if f.suffix in (".ogg", ".webp") else zipfile.ZIP_DEFLATED
            z.writestr(info, f.read_bytes())
    if dest.stat().st_size > MAX_FILE:
        sys.exit(f"{dest.name} is {dest.stat().st_size / 1e6:.1f} MB > jsDelivr 20 MB file limit")
    return dest


def pack_commit(pack_id: str, version: str, zip_path: Path, dry: bool) -> str:
    """Orphan commit whose tree is just <id>.zip; reuses the tag when it already exists."""
    tag = f"pack-{pack_id}-{version}"
    existing = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}^{{commit}}"],
                              cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if existing:
        tree_blob = git("rev-parse", f"{existing}:{pack_id}.zip")
        if tree_blob != git("hash-object", str(zip_path)):
            sys.exit(f"tag {tag} exists with different content: bump the pack version in default.json")
        return existing
    if dry:
        return "<new-commit>"
    blob = git("hash-object", "-w", str(zip_path))
    tree = git("mktree", input=f"100644 blob {blob}\t{pack_id}.zip\n".encode())
    commit = git("commit-tree", tree, "-m", message(f"<add> beat pack {pack_id} {version}"))
    git("tag", tag, commit)
    return commit


def main(argv: list[str]) -> int:
    if not argv or not SEMVER.match(argv[0]):
        sys.exit("usage: publish.py <catalog semver, e.g. 1.1.0> [--dry-run]")
    version, dry = argv[0], "--dry-run" in argv
    if git("tag", "-l", version):
        sys.exit(f"catalog tag {version} already exists")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        sys.exit("run on branch main")

    order = json.loads((PACKS_SRC / "index.json").read_text(encoding="utf-8"))["packs"]
    packs = []
    for pack_id in order:
        info = json.loads((PACKS_SRC / pack_id / "default.json").read_text(encoding="utf-8"))
        zip_path = build_zip(pack_id)
        commit = pack_commit(pack_id, info["version"], zip_path, dry)
        assets = CATALOG_ASSETS / pack_id
        if not dry:
            assets.mkdir(parents=True, exist_ok=True)
            for name in ("cover.webp", "preview.ogg"):
                shutil.copyfile(PACKS_SRC / pack_id / name, assets / name)
        size = zip_path.stat().st_size
        packs.append({
            "id": pack_id,
            "version": info["version"],
            "name": info["name"],
            "genre": info.get("genre", ""),
            "bpm": info["bpm"],
            "key": info["key"],
            "isPremium": bool(info.get("isPremium", False)),
            "description": info.get("short_description", ""),
            "cover": f"packs/{pack_id}/cover.webp",
            "preview": f"packs/{pack_id}/preview.ogg",
            "archive": {
                "url": f"{CDN}@{commit}/{pack_id}.zip",
                "size": size,
                "sha256": sha256(zip_path),
            },
        })
        print(f"{pack_id:18} {info['version']:6} {size / 1e6:5.2f} MB  {commit[:12]}")

    catalog = {"schema": SCHEMA, "version": version, "defaultPackId": order[0], "packs": packs}
    if dry:
        print(json.dumps(catalog, indent=1)[:600], "…")
        return 0
    CATALOG.write_text(json.dumps(catalog, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    tracked = sum(f.stat().st_size for f in ROOT.rglob("*") if f.is_file() and ".git" not in f.parts
                  and "out" not in f.relative_to(ROOT).parts[:1] and ".venv" not in f.parts)
    if tracked > MAX_TREE:
        sys.exit(f"main tree would be {tracked / 1e6:.1f} MB > jsDelivr 50 MB limit")
    git("add", "-A")
    git("commit", "-m", message(f"<add> beat catalog {version}: {len(packs)} packs"))
    git("tag", version)
    print(f"\ncatalog {version}: {CDN}@{version}/catalog.json  (main tree {tracked / 1e6:.1f} MB)")
    print("push: git push origin main --tags")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
