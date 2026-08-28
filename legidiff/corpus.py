"""Build the whole corpus: every Act on the site, resumably.

`build_act` is already incremental for one Act — it reads the versions it has
already committed back out of the log.  This adds the outer loop: which Acts
exist, which have been done, and what went wrong with the ones that didn't, so
a run that dies at Act 9,000 picks up where it stopped.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
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
            fields, checked=datetime.now(timezone.utc).isoformat(timespec="seconds")
        )

    def done(self, ref: fetch.ActRef) -> bool:
        return self.acts.get(str(ref), {}).get("status") == "done"

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
    acts = [ref for ref in fetch.all_acts(cache=cache) if ref.kind in kinds]
    todo = acts if recheck else [ref for ref in acts if not state.done(ref)]
    if limit:
        todo = todo[:limit]
    log(f"{len(acts)} Acts in scope, {len(todo)} to do")

    commits = 0
    for index, ref in enumerate(todo, 1):
        try:
            added = build.build_act(ref, repo, cache=cache, log=lambda message: None)
            commits += added
            state.record(ref, status="done", commits_added=added)
            log(f"[{index}/{len(todo)}] {ref}: {added} new commits")
        except Exception as error:  # noqa: BLE001 - one bad Act must not stop the run
            state.record(ref, status="failed", error=f"{type(error).__name__}: {error}")
            log(f"[{index}/{len(todo)}] {ref}: FAILED {type(error).__name__}: {error}")
        if index % SAVE_EVERY == 0:
            state.save()
    state.save()

    log(f"{commits} commits added; {len(state.failures)} Acts failed")
    return state
