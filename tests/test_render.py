import unittest

from legidiff import render
from tests import fixtures


class SortKeyTests(unittest.TestCase):
    def test_numbers_sort_numerically(self):
        self.assertLess(render.sort_key('7'), render.sort_key('167'))

    def test_letter_suffix_follows_its_number(self):
        self.assertLess(render.sort_key('3'), render.sort_key('3A'))
        self.assertLess(render.sort_key('3A'), render.sort_key('10'))

    def test_alphanumeric_labels(self):
        # The Income Tax Act numbers its sections CW 6, CW 52B.
        self.assertLess(render.sort_key('CW 6'), render.sort_key('CW 52B'))

    def test_spelled_out_schedules(self):
        self.assertEqual(render.sort_key('FIRST SCHEDULE'), '0001')
        self.assertLess(render.sort_key('Second Schedule'), render.sort_key('Third Schedule'))

    def test_unlabelled_provisions_sort_last(self):
        self.assertEqual(render.sort_key(''), '9999')

    def test_no_spaces_in_filenames(self):
        self.assertNotIn(' ', render.sort_key('First Schedule to the Code'))


class SentenceTests(unittest.TestCase):
    def test_splits_on_sentence_ends(self):
        self.assertEqual(
            render.sentences('One thing. Another thing.'),
            ['One thing.', 'Another thing.'],
        )

    def test_does_not_split_on_abbreviations(self):
        self.assertEqual(
            render.sentences('See No. 4 of the list.'),
            ['See No. 4 of the list.'],
        )

    def test_does_not_split_mid_sentence(self):
        self.assertEqual(len(render.sentences('A thing of 5.5 metres in length')), 1)


class InlineTests(unittest.TestCase):
    def parse(self, xml):
        import xml.etree.ElementTree as ET

        return ET.fromstring(xml)

    def test_ids_and_hrefs_are_dropped(self):
        element = self.parse(
            b'<text>See <citation><leg-title href="DLM1" id="LMS2">Other Act 1990'
            b'</leg-title></citation> for details.</text>'
        )
        self.assertEqual(render.inline(element), 'See Other Act 1990 for details.')

    def test_defined_terms_are_bolded(self):
        element = self.parse(b'<text>the <def-term>close of polling</def-term> means</text>')
        self.assertEqual(render.inline(element), 'the **close of polling** means')

    def test_form_fields_become_blanks(self):
        element = self.parse(b'<text>No.<field fill-length="10"/>.</text>')
        self.assertEqual(render.inline(element), 'No.______.')


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.document = render.render(fixtures.MODERN)

    def test_sections_are_named_for_their_label(self):
        self.assertIn('sections/0001-short-title.md', self.document.files)
        self.assertIn('sections/0003a-later-insertion.md', self.document.files)

    def test_subsections_render_as_labelled_items(self):
        text = self.document.files['sections/0001-short-title.md']
        self.assertIn('- **(1)** This is the Example Act 1961.', text)
        self.assertIn('  - **(a)** first thing; and', text)

    def test_repealed_provisions_keep_a_file_and_their_history(self):
        text = self.document.files['sections/0002-gone.md']
        self.assertIn('*[repealed]*', text)
        self.assertIn('Section 2: repealed, on 1 July 2020', text)

    def test_contents_lists_parts_and_sections(self):
        index = self.document.files['index.md']
        self.assertIn('### Part 1: Machinery', index)
        self.assertIn('(sections/0010-tenth.md)', index)

    def test_index_does_not_name_the_version(self):
        # Otherwise every commit would touch it and every diff would open
        # with a line of noise.
        self.assertNotIn('2020-07-01', self.document.files['index.md'])

    def test_front_and_reprint_notes(self):
        self.assertIn('An Act to test things.', self.document.files['front.md'])
        self.assertIn('Reprint notes go here.', self.document.files['reprint-notes.md'])


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.document = render.render(fixtures.MODERN)

    def test_schedule_with_clauses_becomes_a_directory(self):
        self.assertIn('schedules/0001-implied-covenants/index.md', self.document.files)
        self.assertIn('schedules/0001-implied-covenants/0001-payment.md', self.document.files)

    def test_clauses_renumbered_per_part_are_kept_apart(self):
        self.assertIn(
            'schedules/0001-implied-covenants/0001-payment-part-0002.md',
            self.document.files,
        )
        self.assertEqual(len(self.document.collisions), 1)

    def test_schedule_index_links_to_its_clauses(self):
        index = self.document.files['schedules/0001-implied-covenants/index.md']
        self.assertIn('### Part 2: Goods', index)
        self.assertIn('(0001-payment-part-0002.md)', index)

    def test_schedule_without_clauses_stays_one_file(self):
        self.assertIn('schedules/0002-enactments-amended.md', self.document.files)


class OlderDtdTests(unittest.TestCase):
    def setUp(self):
        self.document = render.render(fixtures.OLD)

    def test_version_date_falls_back_when_never_reprinted(self):
        self.assertEqual(self.document.as_at, '1841-06-24')

    def test_enacting_formula_is_kept(self):
        self.assertIn('BE IT ENACTED', self.document.files['front.md'])

    def test_spelled_out_schedule_sorts_by_its_ordinal(self):
        self.assertIn('schedules/0001-forms.md', self.document.files)

    def test_schedule_label_is_not_repeated(self):
        text = self.document.files['schedules/0001-forms.md']
        self.assertTrue(text.startswith('# FIRST SCHEDULE: Forms'), text[:40])

    def test_form_headings_and_signatures_survive(self):
        text = self.document.files['schedules/0001-forms.md']
        self.assertIn('No. 1: General heading', text)
        self.assertIn('Plaintiff.', text)

    def test_nothing_is_dropped(self):
        render.DROPPED.clear()
        render.render(fixtures.OLD)
        self.assertEqual(dict(render.DROPPED), {})


class AmendmentTests(unittest.TestCase):
    def test_history_notes_are_parsed(self):
        import datetime

        document = render.render(fixtures.MODERN)
        (amendment,) = document.amendments
        self.assertEqual(amendment.provision, 'Section 2')
        self.assertEqual(amendment.operation, 'repealed')
        self.assertEqual(amendment.when, datetime.date(2020, 7, 1))
        self.assertEqual(amendment.amending_act, 'Amending Act 2019')


if __name__ == '__main__':
    unittest.main()
