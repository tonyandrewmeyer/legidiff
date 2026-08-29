# legidiff

Builds a git repository of New Zealand Acts, one commit per published version,
so you can read the law's history with `git log`, `git diff` and `git blame`
instead of comparing PDFs by eye.

```
python3 -m legidiff build act/public/1961/43 --repo out/nz-acts

git -C out/nz-acts log --oneline acts/crimes-act-1961/sections/0167-murder-defined.md
git -C out/nz-acts blame acts/crimes-act-1961/sections/0002-interpretation.md
git -C out/nz-acts log -p --since=2020-01-01 acts/crimes-act-1961
```

No dependencies beyond Python 3.11+ and git.

## Where the text comes from

Not the PDFs.  The Parliamentary Counsel Office publishes its own XML for
every version of every Act, and the website serves it without a key:

    https://www.legislation.govt.nz/act/public/1961/43/en/2026-08-08.xml

Version lists come from the site's `/versions/` pages; the list of all Acts
comes from `sitemap.xml`.  Every response is cached under `cache/`, so a
rebuild after changing the renderer costs no requests at all.

There is also an official API at <https://api.legislation.govt.nz> serving the
same data.  It needs a key (10,000 requests/day) and would be the better
citizen for a large crawl; `fetch.py` is the only module that would need to
change.  Note that `robots.txt` disallows URLs with query strings, which
includes page 2+ of a version listing — one more reason to move to the API for
a full-corpus run.  This prototype throttles itself to one request a second.

## Commands

| | |
|---|---|
| `build ACT` | fetch every version, render, commit each one |
| `versions ACT` | list an Act's version identifiers |
| `show ACT DATE [--file index.md]` | render one version without committing |
| `acts` | every Act on the site, from the sitemap |
| `corpus` | build every Act, resumably |
| `update` | commit whatever has been published since the last run |

`ACT` is anything containing a reference, so `act/public/1961/43` or a URL
copied from the browser.  `build` takes `--limit N`, `--since YYYY-MM-DD` and
`--refresh`.

`build` is incremental: it reads the version ids back out of the commit
messages it already wrote and commits only what is new, so a nightly run costs
one version listing plus whatever changed.

`corpus` is the outer loop over every Act, and keeps its own state in
`cache/corpus.json`: which Acts are done, and what went wrong with the ones
that are not.  A run that dies at Act 9,000 resumes where it stopped, and one
bad Act never stops the run.

```
python3 -m legidiff corpus --kinds public          # 14,591 Acts, resumable
python3 -m legidiff corpus --failures              # what did not build
```

## Keeping it up to date

```
python3 -m legidiff update                         # a couple of minutes
python3 -m legidiff update --sweep                 # ask every Act; hours
```

Asking all 14,591 Acts what their current version is costs four hours at one
request a second, which is too much to do nightly for the handful of Acts that
actually change.  So `update` asks the sitemap instead: it carries a `lastmod`
per Act, `corpus.json` records the `lastmod` each Act was built at, and only
the Acts whose page has moved since are worth a look.  A typical night is one
sitemap request and a few dozen Acts — about two minutes.  An Act that is new
to the sitemap has no recorded `lastmod`, so it gets built too.

`lastmod` moves whenever the page changes, not only when a version is
published, so it over-reports rather than under-reports: most of the Acts an
update looks at turn out to have nothing new.  It is still a filter and not a
source of truth, though, so `--sweep` ignores it and asks every Act — worth
running occasionally, and cheap in requests beyond the listing pages, since a
published version's XML is cached forever.

Only the pages that go stale are re-fetched: which version is current, and
what versions exist.

### Nightly, on GitHub Actions

`.github/workflows/update.yml` runs `update` at 19:00 UTC (07:00 NZST) against
the generated repository, which lives in its own repo — `vars.NZ_ACTS_REPO`,
default `tonyandrewmeyer/nz-acts` — cloned, added to and pushed back.  It
needs an `nz-acts` environment holding a `NZ_ACTS_TOKEN` secret with push
rights to that repo.  Build state
rides on an orphan `state` branch there, force-pushed as a single commit each
night, so a runner that has no cache at all still knows what it has already
built.

The initial corpus is *not* built in CI: the first 28,000 commits are pushed
by hand from a machine that has the cache.  The workflow expects the target
repository to exist and already hold that history.

## Tests

```
python3 -m unittest discover -s tests -t .
```

Stdlib `unittest`, no network: the fixtures are small Acts in the shape PCO's
XML actually takes, one modern and one from the older DTD, and the build tests
run real `git` against a temporary repository.

## Layout

```
acts/crimes-act-1961/
    index.md            title, act number, and the contents tree
    front.md            long title
    sections/0167-murder-defined.md
    schedules/0001aa-transitional-savings-and-related-provisions.md
    reprint-notes.md    PCO's own list of amendments included in the reprint
```

A schedule with clauses in it becomes a directory rather than a file, because
some schedules are books — schedule 2 of the Judicature Act 1908 was the whole
High Court Rules, 1,100 rules of them:

```
acts/judicature-act-1908/schedules/0002-high-court-rules/
    index.md                        heading, empowering provision, contents
    0001-0001-title.md              rule 1.1
    0001-0002-objective.md          rule 1.2
    ...
    0001-forms.md                   schedule 1 of the rules
```

Schedules that are prose, tables, forms or lists of amendments have no clauses
to split on, and stay as one file.

## Why it renders the way it does

The whole value of this is diff quality, so the rendering rules all serve it:

* **One file per section**, named from the section's *label* (`0167-`, `0002a-`),
  not its position.  Inserting section 167A doesn't touch any other file, and
  `git blame` on a section stays useful for decades.
* **One sentence per line.**  Amendments are surgical — "omit *fifty*,
  substitute *one hundred*" — and sentence-per-line turns that into a one-line
  diff rather than a reflowed paragraph.
* **No ids, no hrefs.**  PCO regenerates element ids between versions.  Keeping
  them would make every file differ in every version and drown the real changes.
* **The whole Act directory is rewritten each version**, so a repealed section
  shows up as a file deletion.

## Commits

Each commit is dated the day that version took effect (author *and* committer
date, or `git log` sorts them wrongly), authored to the PCO, with a message
built from the version's own history notes:

```
Crimes Act 1961: version as at 2013-07-01

Amendments in force from this date:

- Crimes Amendment Act (No 4) 2011

Provisions affected:

- Section 3: repealed
...
```

## Known limits

* Versions are *reprints* — consolidated snapshots at an effective date — not
  individual amendments.  Several amending Acts can land in one commit.
* Historical coverage varies.  Many Acts have XML back to their enactment, but
  PCO's own caveat is that "as enacted" copies of pre-2008 Acts may not be
  available; where a version won't parse, the build logs it and moves on.
* Older versions use an earlier XML flavour; the renderer handles the common
  elements but has not been exercised against every DTD generation.
* Acts only.  Secondary legislation is deliberately out of scope.

## Status

Prototype.  It builds one Act end to end — the Crimes Act 1961, 60 versions
from 1961 to 2026, in about 60 commits.

The sitemap lists 17,472 Acts (14,591 public, plus local, private, imperial and
provincial).  At an average of a few versions each, a full corpus build is on
the order of 100,000 fetches: a couple of days at one request a second, and
past the point where it should be asking the API for a key and running off a
resumable work queue rather than a for-loop.

Unofficial.  The legislation is Crown copyright with no known re-use
restrictions, but the official PDFs remain authoritative.
