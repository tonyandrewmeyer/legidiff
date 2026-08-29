"""Fetching from legislation.govt.nz, with an on-disk cache and rate limiting.

Everything we need is public: the site serves the PCO's own XML at
``/act/public/{year}/{no}/en/{date}.xml``. The official API
(api.legislation.govt.nz) offers the same data but needs a key, so for now we
stay on the public paths and behave ourselves: one request a second, a real
User-Agent, and every response cached so that a rebuild costs nothing.
"""

import gzip
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE = "https://www.legislation.govt.nz"
USER_AGENT = (
    "legidiff/0.1 (+https://github.com/; builds a git history of NZ legislation; "
    "contact via repo issues)"
)

DEFAULT_CACHE = Path("cache")
MIN_INTERVAL = 1.0  # seconds between requests
MAX_RETRIES = 4

_last_request = 0.0


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActRef:
    """A work, identified the way the website's URLs identify it."""

    kind: str  # "public", "local", "private", "imperial", ...
    year: str
    number: str

    @property
    def path(self) -> str:
        return f"/act/{self.kind}/{self.year}/{self.number}/en"

    @property
    def key(self) -> str:
        return f"act-{self.kind}-{self.year}-{self.number}"

    def __str__(self) -> str:
        return f"act/{self.kind}/{self.year}/{self.number}"


_REF_RE = re.compile(r"/?act/(?P<kind>[a-z]+)/(?P<year>\d{4})/(?P<number>\d+)")


def parse_ref(text: str) -> ActRef:
    """Accept 'act/public/1961/43', a full URL, or anything containing either."""
    match = _REF_RE.search(text)
    if not match:
        raise ValueError(
            f"cannot read an act reference out of {text!r}; "
            "expected something like act/public/1961/43"
        )
    return ActRef(match["kind"], match["year"], match["number"])


def _throttle() -> None:
    global _last_request
    wait = MIN_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def _get(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip",
            "Accept": "*/*",
        },
    )
    for attempt in range(MAX_RETRIES):
        _throttle()
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
                if response.headers.get("x-amzn-waf-action"):
                    # The site is behind AWS WAF, which answers a client it
                    # does not like with 202 and an empty body rather than an
                    # error. Retrying doesn't help, because the challenge
                    # wants a browser. Datacentre IPs get this, home
                    # connections don't.
                    raise FetchError(
                        f"blocked by a WAF challenge for {url}; "
                        "this IP cannot fetch from the site"
                    )
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body
        except urllib.error.HTTPError as error:
            if error.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                time.sleep(5 * 2**attempt)
                continue
            raise FetchError(f"{error.code} for {url}") from error
        except urllib.error.URLError as error:
            if attempt < MAX_RETRIES - 1:
                time.sleep(5 * 2**attempt)
                continue
            raise FetchError(f"{error.reason} for {url}") from error
    raise FetchError(f"gave up on {url}")


def fetch(url: str, cache_path: Path, *, refresh: bool = False) -> bytes:
    """GET *url*, storing the body at *cache_path* and reusing it next time."""
    if cache_path.exists() and not refresh:
        return cache_path.read_bytes()
    body = _get(url)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(body)
    return body


# Version identifiers are usually a date, but where two versions commence on
# the same day PCO suffixes a letter: 2025-11-27, then 2025-11-27B.
_VERSION_ID = re.compile(rb'id="version-(\d{4}-\d{2}-\d{2}[A-Z]?)"')


def version_dates(
    ref: ActRef, *, cache: Path = DEFAULT_CACHE, refresh: bool = False
) -> list[str]:
    """Every published version identifier for *ref*, oldest first.

    The site paginates its version list 50 at a time. The listing is the one
    page that goes stale, so ``--refresh`` re-reads it.
    """
    newest = latest_date(ref, cache=cache, refresh=refresh)
    base = f"{BASE}{ref.path}/{newest}/versions/"
    versions: set[str] = set()
    page = 1
    while True:
        url = base if page == 1 else f"{base}?page={page}"
        try:
            body = fetch(url, cache / ref.key / f"versions-{page}.html", refresh=refresh)
        except FetchError:
            # Acts with a single version have no listing to show.
            break
        found = {match[1].decode() for match in _VERSION_ID.finditer(body)}
        if not found - versions:
            break
        versions |= found
        page += 1
    # The current version is shown as the page you are on rather than as a
    # link, so make sure it is there.
    versions.add(newest)
    if not versions:
        raise FetchError(f"no versions found for {ref}")
    return sorted(versions)


# Acts that were never reprinted (repealed or spent long ago) carry an empty
# date.as.at, and their only version is dated from when they took effect.
# The current version's identifier, taken from the download link on the Act's
# landing page. The XML's own date attributes aren't reliable for this: a
# version that shares its date with another carries a letter suffix
# (2026-05-06B) that appears nowhere in the XML.
_LATEST_ID = re.compile(
    rb'href="/act/[a-z]+/\d{4}/\d+/en/(\d{4}-\d{2}-\d{2}[A-Z]?)\.pdf"'
)

_DATE_ATTRS = [
    re.compile(rb'date\.as\.at="(\d{4}-\d{2}-\d{2})"'),
    re.compile(rb'date\.first\.valid="(\d{4}-\d{2}-\d{2})"'),
    re.compile(rb'date\.assent="(\d{4}-\d{2}-\d{2})"'),
]


def latest_date(
    ref: ActRef, *, cache: Path = DEFAULT_CACHE, refresh: bool = False
) -> str:
    """The identifier of the current version."""
    page = fetch(
        f"{BASE}{ref.path}/latest/",
        cache / ref.key / "latest.html",
        refresh=refresh,
    )
    match = _LATEST_ID.search(page)
    if match:
        return match[1].decode()

    # No download link (some Acts have none): fall back to the XML's dates.
    body = fetch(
        f"{BASE}{ref.path}/latest.xml",
        cache / ref.key / "latest.xml",
        refresh=refresh,
    )
    header = body[:4096]
    for pattern in _DATE_ATTRS:
        match = pattern.search(header)
        if match:
            return match[1].decode()
    raise FetchError(f"no version date in latest.xml for {ref}")


def version_xml(
    ref: ActRef, date: str, *, cache: Path = DEFAULT_CACHE, refresh: bool = False
) -> bytes:
    """The XML of one version. Cached forever: a published version never changes."""
    return fetch(
        f"{BASE}{ref.path}/{date}.xml",
        cache / ref.key / f"{date}.xml",
        refresh=refresh,
    )


# The sitemap carries a <lastmod> for each Act's landing page. It isn't the
# version date (it moves when the page changes for any reason), but it does
# move when a new version is published, which makes it a cheap change filter:
# one request tells us which of 14,000 Acts are worth asking about.
_SITEMAP_ENTRY = re.compile(
    rb"<loc>https://www\.legislation\.govt\.nz(/act/[a-z]+/\d{4}/\d+)/en/latest/</loc>"
    rb"(?:<lastmod>(\d{4}-\d{2}-\d{2})</lastmod>)?"
)


def act_lastmods(
    *, cache: Path = DEFAULT_CACHE, refresh: bool = False
) -> dict[ActRef, str | None]:
    """Every Act on the site and when its page last changed (~5 MB, one request)."""
    body = fetch(f"{BASE}/sitemap.xml", cache / "sitemap.xml", refresh=refresh)
    found: dict[ActRef, str | None] = {}
    for match in _SITEMAP_ENTRY.finditer(body):
        lastmod = match[2].decode() if match[2] else None
        found[parse_ref(match[1].decode())] = lastmod
    if not found:
        raise FetchError(f"no Acts in the sitemap ({len(body)} bytes)")
    return found


def all_acts(*, cache: Path = DEFAULT_CACHE, refresh: bool = False) -> list[ActRef]:
    """Every Act on the site, from its sitemap."""
    refs = act_lastmods(cache=cache, refresh=refresh)
    return sorted(refs, key=lambda r: (r.kind, r.year, int(r.number)))
