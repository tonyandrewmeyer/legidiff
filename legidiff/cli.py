"""Command line entry point: python -m legidiff ..."""

import argparse
import pathlib
import sys

from . import build, corpus, fetch, render


def main(argv: list[str] | None = None) -> int:
    """Run one command, and return the exit status."""
    parser = argparse.ArgumentParser(
        prog='legidiff', description='Build a git history of New Zealand Acts.'
    )
    parser.add_argument('--cache', type=pathlib.Path, default=fetch.DEFAULT_CACHE)
    subparsers = parser.add_subparsers(dest='command', required=True)

    build_parser = subparsers.add_parser('build', help='build the repo for an Act')
    build_parser.add_argument('act', help='e.g. act/public/1961/43, or a page URL')
    build_parser.add_argument('--repo', type=pathlib.Path, default=pathlib.Path('out/nz-acts'))
    build_parser.add_argument('--limit', type=int, help='only the N most recent versions')
    build_parser.add_argument('--since', help='only versions on or after YYYY-MM-DD')
    build_parser.add_argument('--refresh', action='store_true', help='ignore the cache')

    versions_parser = subparsers.add_parser('versions', help="list an Act's versions")
    versions_parser.add_argument('act')
    versions_parser.add_argument('--refresh', action='store_true')

    show_parser = subparsers.add_parser('show', help='render one version to stdout')
    show_parser.add_argument('act')
    show_parser.add_argument('date', help="YYYY-MM-DD, or 'latest'")
    show_parser.add_argument('--file', help='one file from the version, e.g. index.md')

    subparsers.add_parser('acts', help='list every Act on the site')

    corpus_parser = subparsers.add_parser('corpus', help='build every Act, resumably')
    corpus_parser.add_argument('--repo', type=pathlib.Path, default=pathlib.Path('out/nz-acts'))
    corpus_parser.add_argument(
        '--kinds',
        default='public',
        help='comma-separated: public,local,private,imperial,provincial (or all)',
    )
    corpus_parser.add_argument('--limit', type=int, help='stop after N Acts')
    corpus_parser.add_argument(
        '--recheck', action='store_true', help='re-examine Acts already built'
    )
    corpus_parser.add_argument('--failures', action='store_true', help='list what failed and stop')

    update_parser = subparsers.add_parser(
        'update', help='commit whatever has been published since the last run'
    )
    update_parser.add_argument('--repo', type=pathlib.Path, default=pathlib.Path('out/nz-acts'))
    update_parser.add_argument(
        '--kinds',
        default='public',
        help='comma-separated: public,local,private,imperial,provincial (or all)',
    )
    update_parser.add_argument('--limit', type=int, help='stop after N Acts')
    update_parser.add_argument(
        '--sweep',
        action='store_true',
        help="ask every Act, ignoring the sitemap's lastmod filter",
    )

    args = parser.parse_args(argv)

    if args.command == 'acts':
        for ref in fetch.all_acts(cache=args.cache):
            print(ref)
        return 0

    if args.command == 'versions':
        ref = fetch.parse_ref(args.act)
        for version in fetch.version_dates(ref, cache=args.cache, refresh=args.refresh):
            print(version)
        return 0

    if args.command == 'show':
        ref = fetch.parse_ref(args.act)
        version = fetch.latest_date(ref, cache=args.cache) if args.date == 'latest' else args.date
        document = render.render(fetch.version_xml(ref, version, cache=args.cache))
        if args.file:
            text = document.files.get(args.file)
            if text is None:
                print(f'no such file: {args.file}', file=sys.stderr)
                return 1
            print(text, end='')
        else:
            for name in document.files:
                print(name)
        return 0

    if args.command in ('corpus', 'update'):
        if args.command == 'corpus' and args.failures:
            state = corpus.State(args.cache / 'corpus.json')
            for name, record in sorted(state.failures.items()):
                print(f'{name}\t{record["error"]}')
            print(
                f'{len(state.failures)} failed of {len(state.acts)} attempted',
                file=sys.stderr,
            )
            return 0
        all_kinds = ('public', 'local', 'private', 'imperial', 'provincial')
        kinds = all_kinds if args.kinds == 'all' else tuple(args.kinds.split(','))
        if args.command == 'update':
            corpus.update_corpus(
                args.repo,
                kinds=kinds,
                cache=args.cache,
                limit=args.limit,
                sweep=args.sweep,
            )
        else:
            corpus.build_corpus(
                args.repo,
                kinds=kinds,
                cache=args.cache,
                limit=args.limit,
                recheck=args.recheck,
            )
        return 0

    if args.command == 'build':
        ref = fetch.parse_ref(args.act)
        count = build.build_act(
            ref,
            args.repo,
            cache=args.cache,
            limit=args.limit,
            since=args.since,
            refresh=args.refresh,
        )
        print(f'{count} commits in {args.repo}')
        return 0

    return 1


if __name__ == '__main__':
    raise SystemExit(main())
