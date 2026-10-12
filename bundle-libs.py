#!/usr/bin/env python3
"""Fetch NSS, NSPR and libxkbcommon from Gentoo's official binhost and stage
their shared libraries in ~/thorium-build/bundle/lib, so Thorium runs without
installing them system-wide (same idea as firefox-bin bundling its own NSS).

Rerun on every Thorium rebuild to pick up library security updates.
Runtime libs still taken from the system: glibc, sqlite (softokn), zlib.
"""

import hashlib
import io
import re
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

BINHOST = "https://distfiles.gentoo.org/releases/amd64/binpackages/23.0/x86-64-v3"
PACKAGES = ("dev-libs/nspr", "dev-libs/nss", "x11-libs/libxkbcommon")
# Shared objects to keep from each package (matched against basenames).
KEEP = re.compile(
    r"^lib(nspr4|plc4|plds4|nss3|nssutil3|smime3|ssl3|softokn3|freebl3|freeblpriv3"
    r"|nssckbi|xkbcommon|xkbcommon-x11)\.(so(\.[0-9.]+)?|chk)$"
)
DEST = Path.home() / "thorium-build" / "bundle" / "lib"


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def parse_index(text: str) -> list[dict[str, str]]:
    entries = []
    for block in text.split("\n\n")[1:]:
        entry = {}
        for line in block.splitlines():
            key, _, value = line.partition(": ")
            entry[key] = value
        if "CPV" in entry:
            entries.append(entry)
    return entries


def version_key(entry: dict[str, str]) -> tuple:
    match = re.search(r"-([0-9][^-]*)(-r([0-9]+))?$", entry["CPV"])
    version, revision = match.group(1), int(match.group(3) or 0)
    parts = tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[._]", version))
    build_id = int(re.search(r"-(\d+)\.gpkg\.tar$", entry["PATH"]).group(1))
    return parts, revision, build_id


def newest(entries: list[dict[str, str]], package: str) -> dict[str, str]:
    name = re.escape(package)
    candidates = [
        e for e in entries
        if re.fullmatch(rf"{name}-[0-9][^/]*", e["CPV"])
        # Skip the Wayland-enabled libxkbcommon build; X11-only is all we need.
        and not (package == "x11-libs/libxkbcommon" and " wayland" in " " + e.get("USE", ""))
    ]
    if not candidates:
        sys.exit(f"{package}: not found on binhost")
    return max(candidates, key=version_key)


def extract_libs(gpkg: bytes, dest: Path) -> list[str]:
    kept = []
    with tarfile.open(fileobj=io.BytesIO(gpkg)) as outer:
        image = next(m for m in outer.getmembers() if "/image.tar" in m.name)
        inner_bytes = outer.extractfile(image).read()
    with tarfile.open(fileobj=io.BytesIO(inner_bytes)) as inner:
        for member in inner.getmembers():
            base = Path(member.name).name
            if not KEEP.match(base) or "/lib64/" not in member.name:
                continue
            target = dest / base
            target.unlink(missing_ok=True)
            if member.issym():
                if "/" in member.linkname:
                    sys.exit(f"refusing non-local symlink {member.name} -> {member.linkname}")
                target.symlink_to(member.linkname)
            elif member.isfile():
                target.write_bytes(inner.extractfile(member).read())
                target.chmod(0o755 if ".so" in base else 0o644)
            kept.append(base)
    return kept


def main() -> None:
    entries = parse_index(fetch(f"{BINHOST}/Packages").decode())
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    for package in PACKAGES:
        entry = newest(entries, package)
        data = fetch(f"{BINHOST}/{entry['PATH']}")
        digest = hashlib.sha1(data).hexdigest()
        if digest != entry["SHA1"]:
            sys.exit(f"{entry['PATH']}: SHA1 mismatch ({digest} != {entry['SHA1']})")
        kept = extract_libs(data, DEST)
        print(f"{entry['CPV']} ({entry['PATH']}): {' '.join(sorted(kept))}")
    (DEST / "BUNDLED_VERSIONS").write_text(
        "".join(f"{newest(entries, p)['CPV']}\n" for p in PACKAGES)
    )


if __name__ == "__main__":
    main()
