import tempfile
import unittest
from pathlib import Path

from legidiff import corpus, fetch

ACTS = [
    fetch.ActRef("public", "1961", "43"),
    fetch.ActRef("public", "1993", "105"),
    fetch.ActRef("local", "1841", "1"),
]


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = Path(self.directory.name)
        self.attempts = []
        self.fail_on = set()

        original = (corpus.fetch.all_acts, corpus.build.build_act)

        def all_acts(**kwargs):
            return ACTS

        def build_act(ref, repo, **kwargs):
            self.attempts.append(str(ref))
            if str(ref) in self.fail_on:
                raise RuntimeError("boom")
            return 2

        corpus.fetch.all_acts, corpus.build.build_act = all_acts, build_act
        self.addCleanup(
            lambda: setattr(corpus.fetch, "all_acts", original[0])
            or setattr(corpus.build, "build_act", original[1])
        )

    def run_corpus(self, **kwargs):
        return corpus.build_corpus(
            Path(self.directory.name) / "repo",
            cache=self.cache,
            log=lambda message: None,
            **kwargs,
        )

    def test_only_the_requested_kinds(self):
        self.run_corpus()
        self.assertEqual(self.attempts, ["act/public/1961/43", "act/public/1993/105"])

    def test_all_kinds(self):
        self.run_corpus(kinds=("public", "local"))
        self.assertIn("act/local/1841/1", self.attempts)

    def test_a_failure_does_not_stop_the_run(self):
        self.fail_on = {"act/public/1961/43"}
        state = self.run_corpus()
        self.assertEqual(len(self.attempts), 2)
        self.assertEqual(list(state.failures), ["act/public/1961/43"])
        self.assertIn("RuntimeError: boom", state.failures["act/public/1961/43"]["error"])

    def test_resuming_skips_what_is_done_and_retries_what_failed(self):
        self.fail_on = {"act/public/1993/105"}
        self.run_corpus()
        self.attempts.clear()
        self.fail_on.clear()
        state = self.run_corpus()
        self.assertEqual(self.attempts, ["act/public/1993/105"])
        self.assertEqual(state.failures, {})

    def test_recheck_revisits_everything(self):
        self.run_corpus()
        self.attempts.clear()
        self.run_corpus(recheck=True)
        self.assertEqual(len(self.attempts), 2)

    def test_limit(self):
        self.run_corpus(limit=1)
        self.assertEqual(self.attempts, ["act/public/1961/43"])

    def test_state_survives_a_new_process(self):
        self.run_corpus()
        state = corpus.State(self.cache / "corpus.json")
        self.assertTrue(state.done(ACTS[0]))
        self.assertEqual(state.acts["act/public/1961/43"]["commits_added"], 2)


if __name__ == "__main__":
    unittest.main()
