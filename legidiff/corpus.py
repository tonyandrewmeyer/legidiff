"""Build the whole corpus: every Act on the site, resumably.

`build_act` is already incremental for one Act, since it reads the versions
it has already committed back out of the log. This adds the outer loop: which
Acts exist, which have been done, and what went wrong with the ones that
didn't, so that a run which dies at Act 9,000 picks up where it stopped.

`update_corpus` is the same loop run nightly. Asking all 14,000 Acts what
their current version is costs four hours at one request a second, so it asks
the sitemap instead: that carries a `lastmod` per Act, and only the Acts whose
`lastmod` has moved since the last run are worth a look. It's a filter rather
than a source of truth, so `--sweep` ignores it and checks everything.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from . import build, fetch

SAVE_EVERY = 10


class State:
    """What has been built, kept on disk so a run can be resumed."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.acts: dict[str, dict] = {}
        if path.exists():
            self.acts = json.loads(path.read_text()).get("acts", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"acts": self.acts}, indent=1, sort_keys=True))

    def record(self, ref: fetch.ActRef, **fields) -> None:
        self.acts[str(ref)] = dict(
            fields, checked=datetime.now(UTC).isoformat(timespec="seconds")
        )

    def done(self, ref: fetch.ActRef) -> bool:
        return self.acts.get(str(ref), {}).get("status") == "done"

    def stale(self, ref: fetch.ActRef, lastmod: str | None) -> bool:
        """Is this Act unbuilt, or has its page changed since we last looked?"""
        record = self.acts.get(str(ref))
        if record is None or record.get("status") != "done":
            return True
        return record.get("lastmod") != lastmod

    @property
    def failures(self) -> dict[str, dict]:
        return {k: v for k, v in self.acts.items() if v.get("status") == "failed"}


def build_corpus(
    repo: Path,
    *,
    kinds: tuple[str, ...] = ("public",),
    cache: Path = fetch.DEFAULT_CACHE,
    state_path: Path | None = None,
    limit: int | None = None,
    recheck: bool = False,
    log=lambda message: print(message, flush=True),
) -> State:
    state = State(state_path or cache / "corpus.json")
    lastmods = fetch.act_lastmods(cache=cache)
    acts = [ref for ref in sorted_acts(lastmods) if ref.kind in kinds]
    todo = acts if recheck else [ref for ref in acts if not state.done(ref)]
    if limit:
        todo = todo[:limit]
    log(f"{len(acts)} Acts in scope, {len(todo)} to do")

    commits = 0
    for index, ref in enumerate(todo, 1):
        try:
            added = build.build_act(ref, repo, cache=cache, log=lambda message: None)
            commits += added
            state.record(
                ref, status="done", commits_added=added, lastmod=lastmods.get(ref)
            )
            log(f"[{index}/{len(todo)}] {ref}: {added} new commits")
        except Exception as error:  # noqa: BLE001 - one bad Act must not stop the run
            state.record(ref, status="failed", error=f"{type(error).__name__}: {error}")
            log(f"[{index}/{len(todo)}] {ref}: FAILED {type(error).__name__}: {error}")
        if index % SAVE_EVERY == 0:
            state.save()
    state.save()

    log(f"{commits} commits added; {len(state.failures)} Acts failed")
    return state


def sorted_acts(refs) -> list[fetch.ActRef]:
    return sorted(refs, key=lambda r: (r.kind, r.year, int(r.number)))


def update_corpus(
    repo: Path,
    *,
    kinds: tuple[str, ...] = ("public",),
    cache: Path = fetch.DEFAULT_CACHE,
    state_path: Path | None = None,
    limit: int | None = None,
    sweep: bool = False,
    log=lambda message: print(message, flush=True),
) -> State:
    """Commit whatever has been published since the last run.

    One request for the sitemap, then a look at each Act whose page has
    changed since we last built it. New Acts are included too, since an Act
    we've never seen has no recorded `lastmod` to match.
    """
    state = State(state_path or cache / "corpus.json")
    lastmods = fetch.act_lastmods(cache=cache, refresh=True)
    acts = [ref for ref in sorted_acts(lastmods) if ref.kind in kinds]
    todo = acts if sweep else [ref for ref in acts if state.stale(ref, lastmods[ref])]
    if limit:
        todo = todo[:limit]
    log(f"{len(acts)} Acts in scope, {len(todo)} changed since the last run")

    commits = 0
    changed: list[str] = []
    for index, ref in enumerate(todo, 1):
        try:
            added = build.build_act(
                ref, repo, cache=cache, refresh_listing=True, log=lambda message: None
            )
            commits += added
            state.record(
                ref, status="done", commits_added=added, lastmod=lastmods.get(ref)
            )
            if added:
                changed.append(str(ref))
            log(f"[{index}/{len(todo)}] {ref}: {added} new commits")
        except Exception as error:  # noqa: BLE001 - one bad Act must not stop the run
            # No lastmod is recorded for a failure, so the next run retries it.
            state.record(ref, status="failed", error=f"{type(error).__name__}: {error}")
            log(f"[{index}/{len(todo)}] {ref}: FAILED {type(error).__name__}: {error}")
        if index % SAVE_EVERY == 0:
            state.save()
    state.save()

    log(f"{commits} commits added across {len(changed)} Acts; {len(state.failures)} failed")
    return state
