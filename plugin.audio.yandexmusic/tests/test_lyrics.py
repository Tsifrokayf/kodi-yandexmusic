import unittest

import _bootstrap  # noqa: F401

from ymkodi.lyrics import line_index, parse_lrc, plain_from_lrc


class ParseLrcTest(unittest.TestCase):
    def test_basic_lines_sorted(self):
        text = '[00:12.50]second\n[00:03]first\n'
        self.assertEqual(parse_lrc(text), [(3.0, 'first'), (12.5, 'second')])

    def test_multiple_tags_on_one_line(self):
        text = '[00:01][00:31]chorus\n'
        self.assertEqual(parse_lrc(text), [(1.0, 'chorus'), (31.0, 'chorus')])

    def test_extra_colon_treated_as_fraction(self):
        text = '[01:02:03]odd\nplain line\n'
        self.assertEqual(parse_lrc(text), [(62.03, 'odd')])

    def test_fraction_padding(self):
        self.assertEqual(parse_lrc('[00:01.5]x'), [(1.5, 'x')])
        self.assertEqual(parse_lrc('[00:01.123456]x'), [(1.123, 'x')])

    def test_empty(self):
        self.assertEqual(parse_lrc(''), [])
        self.assertEqual(parse_lrc(None), [])

    def test_tag_without_text_skipped(self):
        self.assertEqual(parse_lrc('[00:05]\n[00:06]text'), [(6.0, 'text')])


class PlainFromLrcTest(unittest.TestCase):
    def test_strips_tags_keeps_lines(self):
        text = '[00:01.00]hello\n[00:02.00]world\n'
        self.assertEqual(plain_from_lrc(text), 'hello\nworld')

    def test_mixed_lines(self):
        text = '[00:01]a\nplain b\n'
        self.assertEqual(plain_from_lrc(text), 'a\nplain b')

    def test_empty(self):
        self.assertEqual(plain_from_lrc(None), '')


class LineIndexTest(unittest.TestCase):
    ENTRIES = [(10.0, 'a'), (20.0, 'b'), (30.0, 'c')]

    def test_before_first(self):
        self.assertEqual(line_index(self.ENTRIES, 5.0), -1)

    def test_on_boundary(self):
        self.assertEqual(line_index(self.ENTRIES, 10.0), 0)
        self.assertEqual(line_index(self.ENTRIES, 20.0), 1)

    def test_between(self):
        self.assertEqual(line_index(self.ENTRIES, 25.0), 1)

    def test_after_last(self):
        self.assertEqual(line_index(self.ENTRIES, 99.0), 2)

    def test_empty(self):
        self.assertEqual(line_index([], 5.0), -1)


if __name__ == '__main__':
    unittest.main()
