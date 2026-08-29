import tempfile
import unittest
from pathlib import Path

from legidiff import corpus, fetch

ACTS = [
    fetch.ActRef('public', '1961', '43'),
    fetch.ActRef('public', '1993', '105'),
    fetch.ActRef('local', '1841', '1'),
]


class FakeSite(unittest.TestCase):
    """A site of three Acts, and a build_act that records what it was asked."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = Path(self.directory.name)
        self.attempts = []
        self.fail_on = set()

        self.lastmods = {ref: '2026-08-01' for ref in ACTS}
        self.commits = 2

        original = (corpus.fetch.act_lastmods, corpus.build.build_act)

        def act_lastmods(**kwargs):
            return dict(self.lastmods)

        def build_act(ref, repo, **kwargs):
            self.attempts.append(str(ref))
            if str(ref) in self.fail_on:
                raise RuntimeError('boom')
            return self.commits

        corpus.fetch.act_lastmods, corpus.build.build_act = act_lastmods, build_act
        self.addCleanup(
            lambda: setattr(corpus.fetch, 'act_lastmods', original[0])
            or setattr(corpus.build, 'build_act', original[1])
        )

    def run_corpus(self, **kwargs):
        return corpus.build_corpus(
            Path(self.directory.name) / 'repo',
            cache=self.cache,
            log=lambda message: None,
            **kwargs,
        )

    def run_update(self, **kwargs):
        return corpus.update_corpus(
            Path(self.directory.name) / 'repo',
            cache=self.cache,
            log=lambda message: None,
            **kwargs,
        )


class CorpusTests(FakeSite):
    """The full build: everything not already done."""

    def test_only_the_requested_kinds(self):
        self.run_corpus()
        self.assertEqual(self.attempts, ['act/public/1961/43', 'act/public/1993/105'])

    def test_all_kinds(self):
        self.run_corpus(kinds=('public', 'local'))
        self.assertIn('act/local/1841/1', self.attempts)

    def test_a_failure_does_not_stop_the_run(self):
        self.fail_on = {'act/public/1961/43'}
        state = self.run_corpus()
        self.assertEqual(len(self.attempts), 2)
        self.assertEqual(list(state.failures), ['act/public/1961/43'])
        self.assertIn('RuntimeError: boom', state.failures['act/public/1961/43']['error'])

    def test_resuming_skips_what_is_done_and_retries_what_failed(self):
        self.fail_on = {'act/public/1993/105'}
        self.run_corpus()
        self.attempts.clear()
        self.fail_on.clear()
        state = self.run_corpus()
        self.assertEqual(self.attempts, ['act/public/1993/105'])
        self.assertEqual(state.failures, {})

    def test_recheck_revisits_everything(self):
        self.run_corpus()
        self.attempts.clear()
        self.run_corpus(recheck=True)
        self.assertEqual(len(self.attempts), 2)

    def test_limit(self):
        self.run_corpus(limit=1)
        self.assertEqual(self.attempts, ['act/public/1961/43'])

    def test_state_survives_a_new_process(self):
        self.run_corpus()
        state = corpus.State(self.cache / 'corpus.json')
        self.assertTrue(state.done(ACTS[0]))
        self.assertEqual(state.acts['act/public/1961/43']['commits_added'], 2)


class UpdateTests(FakeSite):
    """The nightly loop: only Acts whose sitemap entry has moved."""

    def test_an_unchanged_act_is_not_asked_about(self):
        self.run_corpus()
        self.attempts.clear()
        self.run_update()
        self.assertEqual(self.attempts, [])

    def test_a_changed_act_is_rebuilt(self):
        self.run_corpus()
        self.attempts.clear()
        self.lastmods[ACTS[0]] = '2026-08-29'
        self.run_update()
        self.assertEqual(self.attempts, ['act/public/1961/43'])

    def test_an_act_that_is_new_to_the_sitemap_is_built(self):
        self.run_corpus()
        self.attempts.clear()
        new = fetch.ActRef('public', '2026', '1')
        self.lastmods[new] = '2026-08-29'
        self.run_update()
        self.assertEqual(self.attempts, ['act/public/2026/1'])

    def test_a_failure_is_retried_next_run(self):
        self.fail_on = {'act/public/1961/43'}
        self.run_update()
        self.attempts.clear()
        self.fail_on.clear()
        state = self.run_update()
        self.assertEqual(self.attempts, ['act/public/1961/43'])
        self.assertEqual(state.failures, {})

    def test_sweep_ignores_the_filter(self):
        self.run_corpus()
        self.attempts.clear()
        self.run_update(sweep=True)
        self.assertEqual(self.attempts, ['act/public/1961/43', 'act/public/1993/105'])

    def test_the_listing_is_refreshed_but_the_cached_xml_is_not(self):
        seen = []
        corpus.build.build_act = lambda ref, repo, **kwargs: seen.append(kwargs) or 0
        self.run_update()
        self.assertTrue(all(kwargs['refresh_listing'] for kwargs in seen))
        self.assertTrue(all(not kwargs.get('refresh') for kwargs in seen))


if __name__ == '__main__':
    unittest.main()
