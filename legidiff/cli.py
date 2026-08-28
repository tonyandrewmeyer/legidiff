"""Command line entry point: python -m legidiff ..."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import build, fetch, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="legidiff", description="Build a git history of New Zealand Acts."
    )
    parser.add_argument("--cache", type=Path, default=fetch.DEFAULT_CACHE)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="build the repo for an Act")
    build_parser.add_argument("act", help="e.g. act/public/1961/43, or a page URL")
    build_parser.add_argument("--repo", type=Path, default=Path("out/nz-acts"))
    build_parser.add_argument("--limit", type=int, help="only the N most recent versions")
    build_parser.add_argument("--since", help="only versions on or after YYYY-MM-DD")
    build_parser.add_argument("--refresh", action="store_true", help="ignore the cache")

    versions_parser = subparsers.add_parser("versions", help="list an Act's versions")
    versions_parser.add_argument("act")
    versions_parser.add_argument("--refresh", action="store_true")

    show_parser = subparsers.add_parser("show", help="render one version to stdout")
    show_parser.add_argument("act")
    show_parser.add_argument("date", help="YYYY-MM-DD, or 'latest'")
    show_parser.add_argument("--file", help="one file from the version, e.g. index.md")

    subparsers.add_parser("acts", help="list every Act on the site")

    args = parser.parse_args(argv)

    if args.command == "acts":
        for ref in fetch.all_acts(cache=args.cache):
            print(ref)
        return 0

    if args.command == "versions":
        ref = fetch.parse_ref(args.act)
        for version in fetch.version_dates(ref, cache=args.cache, refresh=args.refresh):
            print(version)
        return 0

    if args.command == "show":
        ref = fetch.parse_ref(args.act)
        version = (
            fetch.latest_date(ref, cache=args.cache) if args.date == "latest" else args.date
        )
        document = render.render(fetch.version_xml(ref, version, cache=args.cache))
        if args.file:
            text = document.files.get(args.file)
            if text is None:
                print(f"no such file: {args.file}", file=sys.stderr)
                return 1
            print(text, end="")
        else:
            for name in document.files:
                print(name)
        return 0

    if args.command == "build":
        ref = fetch.parse_ref(args.act)
        count = build.build_act(
            ref,
            args.repo,
            cache=args.cache,
            limit=args.limit,
            since=args.since,
            refresh=args.refresh,
        )
        print(f"{count} commits in {args.repo}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
