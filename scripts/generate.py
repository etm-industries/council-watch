#!/usr/bin/env python3
"""Static site generation script — renders HTML from canonical JSON data.

Usage:
    uv run python scripts/generate.py [--data-dir PATH] [--output-dir PATH]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from council_watch.site.generator import build_site
from council_watch.store import DataStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Council Watch static site")
    parser.add_argument("--data-dir", default="data", help="Path to data store directory")
    parser.add_argument("--output-dir", default="site", help="Output directory for static site")
    parser.add_argument("--base-url", default="", help="Base URL prefix (e.g. /council-watch)")
    parser.add_argument(
        "--site-title", default="Council Watch Austin", help="Site display title"
    )
    args = parser.parse_args()

    store = DataStore(args.data_dir)
    build_site(
        store,
        args.output_dir,
        site_title=args.site_title,
        base_url=args.base_url,
    )


if __name__ == "__main__":
    main()
