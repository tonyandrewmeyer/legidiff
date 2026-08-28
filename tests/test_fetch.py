import unittest

from legidiff import fetch


class ParseRefTests(unittest.TestCase):
    def test_bare_reference(self):
        self.assertEqual(fetch.parse_ref("act/public/1961/43"), fetch.ActRef("public", "1961", "43"))

    def test_url_from_the_browser(self):
        self.assertEqual(
            fetch.parse_ref("https://www.legislation.govt.nz/act/public/1961/43/en/latest/"),
            fetch.ActRef("public", "1961", "43"),
        )

    def test_other_kinds(self):
        self.assertEqual(fetch.parse_ref("act/imperial/1267/23").kind, "imperial")

    def test_rejects_nonsense(self):
        with self.assertRaises(ValueError):
            fetch.parse_ref("the Crimes Act")

    def test_path_and_cache_key(self):
        ref = fetch.parse_ref("act/local/1841/1")
        self.assertEqual(ref.path, "/act/local/1841/1/en")
        self.assertEqual(ref.key, "act-local-1841-1")


class ScrapeTests(unittest.TestCase):
    def test_version_ids_include_letter_suffixes(self):
        page = b'<div id="version-2025-11-27"></div><div id="version-2025-11-27B"></div>'
        self.assertEqual(
            [match[1].decode() for match in fetch._VERSION_ID.finditer(page)],
            ["2025-11-27", "2025-11-27B"],
        )

    def test_current_version_comes_from_the_download_link(self):
        # The suffix on a same-day version appears nowhere in the XML, so the
        # landing page is the only place to learn the real identifier.
        page = b'<a href="/act/private/2026/1/en/2026-05-06B.pdf">Download</a>'
        self.assertEqual(fetch._LATEST_ID.search(page)[1], b"2026-05-06B")

    def test_date_attributes_are_tried_in_order(self):
        never_reprinted = (
            b'<act act.no="66" date.as.at="" date.assent="1975-10-09" '
            b'date.first.valid="1975-10-10">'
        )
        found = [
            pattern.search(never_reprinted) for pattern in fetch._DATE_ATTRS
        ]
        self.assertIsNone(found[0])
        self.assertEqual(found[1][1], b"1975-10-10")
        self.assertEqual(found[2][1], b"1975-10-09")

    def test_sitemap_yields_act_references(self):
        sitemap = (
            b"<loc>https://www.legislation.govt.nz/act/public/1961/43/en/latest/</loc>"
            b"<loc>https://www.legislation.govt.nz/regulation/public/2020/1/en/latest/</loc>"
        )
        found = [match[1].decode() for match in fetch._SITEMAP_ACT.finditer(sitemap)]
        self.assertEqual(found, ["/act/public/1961/43"])


if __name__ == "__main__":
    unittest.main()
