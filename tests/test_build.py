import datetime
import subprocess
import tempfile
import unittest
from pathlib import Path

from legidiff import build, fetch, render
from tests import fixtures

REF = fetch.ActRef("public", "1961", "43")


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout


class VersionDateTests(unittest.TestCase):
    def test_plain_date(self):
        self.assertEqual(build.version_date("2020-07-01"), datetime.date(2020, 7, 1))

    def test_suffixed_version_id(self):
        # Two versions commencing the same day: 2025-11-27, then 2025-11-27B.
        self.assertEqual(build.version_date("2025-11-27B"), datetime.date(2025, 11, 27))


class CommitMessageTests(unittest.TestCase):
    def setUp(self):
        self.document = render.render(fixtures.MODERN)
        self.document.source_path = "/act/public/1961/43/2020-07-01"

    def test_names_the_amending_act_in_force_that_day(self):
        message = build.commit_message(self.document, "2020-07-01", first=False)
        self.assertIn("Example Act 1961: version as at 2020-07-01", message)
        self.assertIn("- Amending Act 2019", message)
        self.assertIn("- Section 2: repealed", message)

    def test_ignores_amendments_from_other_dates(self):
        message = build.commit_message(self.document, "2019-01-01", first=False)
        self.assertNotIn("Amending Act 2019", message)

    def test_keeps_the_full_version_id_in_the_subject(self):
        message = build.commit_message(self.document, "2025-11-27B", first=False)
        self.assertIn("version as at 2025-11-27B", message)

    def test_pre_epoch_dates_are_explained(self):
        message = build.commit_message(self.document, "1841-06-24", first=True)
        self.assertIn("Version-Date: 1841-06-24", message)
        self.assertIn("git cannot date a commit before 1970", message)


class BuildTests(unittest.TestCase):
    """Build a repository end to end, with the network stubbed out."""

    versions = {"1961-11-01": fixtures.OLD, "2020-07-01": fixtures.MODERN}

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repo = Path(self.directory.name) / "repo"
        self.addCleanup(self.directory.cleanup)

        original = (fetch.version_dates, fetch.version_xml)

        def version_dates(ref, **kwargs):
            return sorted(self.versions)

        def version_xml(ref, version, **kwargs):
            return self.versions[version]

        fetch.version_dates, fetch.version_xml = version_dates, version_xml
        build.fetch.version_dates, build.fetch.version_xml = version_dates, version_xml

        def restore():
            fetch.version_dates, fetch.version_xml = original
            build.fetch.version_dates, build.fetch.version_xml = original

        self.addCleanup(restore)

    def build(self, **kwargs):
        return build.build_act(REF, self.repo, log=lambda message: None, **kwargs)

    def test_one_commit_per_version(self):
        self.assertEqual(self.build(), 2)
        subjects = git(self.repo, "log", "--format=%s").splitlines()
        self.assertEqual(
            subjects,
            [
                "Example Act 1961: version as at 2020-07-01",
                "Old Act 1841: version as at 1961-11-01",
                "Initial commit",
            ],
        )

    def test_commits_are_dated_from_the_version(self):
        self.build()
        dates = git(self.repo, "log", "--format=%ad", "--date=short").splitlines()
        self.assertEqual(dates[0], "2020-07-01")

    def test_the_act_directory_is_named_for_the_current_title(self):
        # The 1841 version has a different title; history stays in one place.
        self.build()
        self.assertTrue((self.repo / "acts" / "example-act-1961").is_dir())
        self.assertFalse((self.repo / "acts" / "old-act-1841").exists())

    def test_provisions_that_go_away_are_deleted(self):
        self.build()
        changes = git(self.repo, "show", "--name-status", "--format=", "HEAD")
        self.assertIn("D\tacts/example-act-1961/schedules/0001-forms.md", changes)

    def test_rebuilding_adds_nothing(self):
        self.build()
        self.assertEqual(self.build(), 0)

    def test_a_version_with_no_textual_change_is_skipped(self):
        self.versions = dict(self.versions, **{"2021-01-01": fixtures.MODERN})
        self.assertEqual(self.build(), 2)

    def test_pre_epoch_versions_still_commit(self):
        self.versions = {"1841-06-24": fixtures.OLD}
        self.assertEqual(self.build(), 1)
        self.assertEqual(
            git(self.repo, "log", "-1", "--format=%ad", "--date=short").strip(),
            "1970-01-01",
        )
        self.assertIn("Version-Date: 1841-06-24", git(self.repo, "log", "-1", "--format=%b"))


if __name__ == "__main__":
    unittest.main()
