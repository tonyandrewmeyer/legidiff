"""Build the git repository: one commit per published version of an Act."""

from __future__ import annotations

import re
import shutil
import subprocess
from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path

from . import fetch, render

# git cannot represent commit dates before the Unix epoch, so versions older
# than this get an epoch commit date; the true date stays in the message.
EPOCH = date(1970, 1, 1)

AUTHOR_NAME = "New Zealand Parliamentary Counsel Office"
AUTHOR_EMAIL = "noreply@pco.govt.nz"

REPO_README = """# NZ legislation, as a git history

Each commit is one published version of an Act, taken from the XML that the
Parliamentary Counsel Office publishes at <https://www.legislation.govt.nz>,
rendered to markdown, and committed with the date that version took effect.

So:

    git log --oneline acts/crimes-act-1961/sections/0167-murder-defined.md
    git blame acts/crimes-act-1961/sections/0002-interpretation.md
    git log -p --since=2020-01-01 acts/crimes-act-1961

This repository is generated.  Do not commit to it by hand — it gets rebuilt.
The legislation itself is Crown copyright and free of known re-use
restrictions; this rendering is unofficial, and the PDFs on the official site
remain the authoritative version.
"""


def version_date(version: str) -> date:
    """A version id is a date, sometimes with a disambiguating letter suffix."""
    return datetime.fromisoformat(version[:10]).date()


def run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, check=True
    )
    return result.stdout


def ensure_repo(repo: Path) -> None:
    if (repo / ".git").exists():
        return
    repo.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q", "-b", "main"], repo)
    run(["git", "config", "user.name", AUTHOR_NAME], repo)
    run(["git", "config", "user.email", AUTHOR_EMAIL], repo)
    (repo / "README.md").write_text(REPO_README)
    run(["git", "add", "README.md"], repo)
    commit(repo, "Initial commit", date(1970, 1, 1))


def commit(repo: Path, message: str, when: date) -> None:
    import os

    stamp = f"{max(when, EPOCH).isoformat()}T12:00:00+12:00"
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_DATE=stamp,
        GIT_COMMITTER_DATE=stamp,
        GIT_AUTHOR_NAME=AUTHOR_NAME,
        GIT_AUTHOR_EMAIL=AUTHOR_EMAIL,
        GIT_COMMITTER_NAME=AUTHOR_NAME,
        GIT_COMMITTER_EMAIL=AUTHOR_EMAIL,
    )
    run(["git", "commit", "-q", "--no-gpg-sign", "-m", message], repo, env)


def commit_message(document: render.Document, version: str, first: bool) -> str:
    """Describe a version by the amendments that came into force on its date."""
    when = version_date(version)
    lines = [f"{document.title}: version as at {version}"]
    if first:
        lines += ["", "First version available from the NZ Legislation website."]

    todays = [a for a in document.amendments if a.when == when]
    acts = list(OrderedDict.fromkeys(a.amending_act for a in todays if a.amending_act))
    if acts:
        lines += ["", "Amendments in force from this date:", ""]
        lines += [f"- {act}" for act in acts]

    changes = list(
        OrderedDict.fromkeys(
            f"{a.provision}: {a.operation}"
            for a in todays
            if a.provision and a.operation
        )
    )
    if changes:
        lines += ["", "Provisions affected:", ""]
        lines += [f"- {change}" for change in changes[:40]]
        if len(changes) > 40:
            lines.append(f"- ... and {len(changes) - 40} more")

    lines += ["", f"Version-Date: {when.isoformat()}"]
    if when < EPOCH:
        lines.append(
            "Note: git cannot date a commit before 1970, so the commit date is "
            "the epoch; Version-Date above is the real one."
        )
    lines += [f"Source: {fetch.BASE}{document.source_path}"]
    return "\n".join(lines) + "\n"


_SOURCE = re.compile(r"^Source: \S+(/act/\S+)$", re.MULTILINE)


def committed_versions(repo: Path, ref: fetch.ActRef) -> set[str]:
    """Version ids this repo already has, read back out of the commit messages.

    Lets a nightly run add only what is new instead of rebuilding history.
    """
    log = run(["git", "log", "--format=%B"], repo)
    prefix = f"{ref.path}/"
    return {
        match[1][len(prefix):]
        for match in _SOURCE.finditer(log)
        if match[1].startswith(prefix)
    }


def write_document(target: Path, document: render.Document) -> None:
    """Replace *target* with this version's files, so deletions show as deletions."""
    if target.exists():
        shutil.rmtree(target)
    for name, text in document.files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def build_act(
    ref: fetch.ActRef,
    repo: Path,
    *,
    cache: Path = fetch.DEFAULT_CACHE,
    limit: int | None = None,
    since: str | None = None,
    refresh: bool = False,
    log=lambda message: print(message, flush=True),
) -> int:
    ensure_repo(repo)
    dates = fetch.version_dates(ref, cache=cache, refresh=refresh)
    done = committed_versions(repo, ref)
    if since:
        dates = [d for d in dates if d >= since]
    if limit:
        dates = dates[-limit:]
    log(f"{ref}: {len(dates)} versions ({dates[0]} to {dates[-1]})")

    # The Act's directory is named for its *current* title, so that a renamed
    # Act keeps one continuous history rather than splitting in two.
    slug = render.slugify(
        render.render(fetch.version_xml(ref, dates[-1], cache=cache)).title
    )
    target = repo / "acts" / slug

    committed = 0
    for index, version in enumerate(dates):
        if version in done:
            continue
        try:
            xml = fetch.version_xml(ref, version, cache=cache, refresh=refresh)
            document = render.render(xml)
        except Exception as error:  # noqa: BLE001 - one bad version shouldn't stop the run
            log(f"  {version}: skipped ({type(error).__name__}: {error})")
            continue
        document.source_path = f"{ref.path}/{version}"
        write_document(target, document)
        run(["git", "add", "-A", "--", str(target.relative_to(repo))], repo)
        if not run(["git", "diff", "--cached", "--name-only"], repo).strip():
            log(f"  {version}: no textual change, skipped")
            continue
        commit(repo, commit_message(document, version, index == 0), version_date(version))
        committed += 1
        log(f"  {version}: committed")
    return committed
