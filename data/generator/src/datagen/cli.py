"""Writes every company's SQL files under data/.

    uv run datagen          # write the files
    uv run datagen --check  # fail if any file is out of date
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .companies import scripts
from .dialects import DIALECTS
from .render import render

DATA_DIR = Path(__file__).resolve().parents[3]


def generate() -> dict[Path, str]:
    return {DATA_DIR / s.path: render(s, DIALECTS[s.platform]) for s in scripts()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail if any generated file is out of date")
    args = parser.parse_args(argv)

    stale = []
    for path, text in generate().items():
        current = path.read_text() if path.exists() else None
        if current == text:
            continue
        stale.append(path)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        print(f"{'out of date' if args.check else 'wrote'}: {path.relative_to(DATA_DIR)} ({len(text) // 1024} KB)")
    if args.check and stale:
        print("Run `make data` to regenerate.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
