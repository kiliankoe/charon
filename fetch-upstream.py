#!/usr/bin/env python3
"""Download the official Bone and NeoQwertz keylayouts into upstream/.

The files come from the Neo project's primary repository at git.neo-layout.org,
pinned to a commit. The GitHub mirror is not used: it stopped following the
primary in 2022 and lacks the 2024 rework of the macOS bundle.
"""

import pathlib
import urllib.parse
import urllib.request

COMMIT = "cf36e07ce5ff22c51149c3ad933c71fcd770f613"  # master, 2026-03-13
BASE = f"https://git.neo-layout.org/neo/neo-layout/raw/commit/{COMMIT}/mac_osx/neo-layouts.bundle/Contents/Resources/"
FILES = ["Deutsch (Bone).keylayout", "Deutsch (NeoQwertz).keylayout"]


def main() -> None:
    out = pathlib.Path(__file__).parent / "upstream"
    out.mkdir(exist_ok=True)
    for name in FILES:
        url = BASE + urllib.parse.quote(name)
        with urllib.request.urlopen(url) as resp:
            (out / name).write_bytes(resp.read())
        print(f"fetched {name} from {url}")
    (out / "COMMIT").write_text(COMMIT + "\n")


if __name__ == "__main__":
    main()
