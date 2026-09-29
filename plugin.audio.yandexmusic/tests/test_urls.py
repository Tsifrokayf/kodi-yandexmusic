import unittest

import _bootstrap  # noqa: F401

from ymkodi.urls import BASE_URL, build_url, parse_params


class BuildUrlTest(unittest.TestCase):
    def test_action_only(self):
        self.assertEqual(build_url(BASE_URL, 'root'), BASE_URL + '?action=root')

    def test_params_are_encoded(self):
        url = build_url(BASE_URL, 'search_results', type='track', q='комета & луна')
        self.assertIn('q=%D0%BA%D0%BE%D0%BC%D0%B5%D1%82%D0%B0', url)
        self.assertIn('%26', url)

    def test_empty_params_skipped(self):
        url = build_url(BASE_URL, 'album', id='42', page=None, q='')
        self.assertEqual(url, BASE_URL + '?action=album&id=42')

    def test_numeric_params_stringified(self):
        url = build_url(BASE_URL, 'playlist', uid=100, kind=200)
        self.assertEqual(url, BASE_URL + '?action=playlist&uid=100&kind=200')


class ParseParamsTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(parse_params(''), {})
        self.assertEqual(parse_params(None), {})

    def test_roundtrip(self):
        url = build_url(BASE_URL, 'station', station='track:123', name='Мой трек')
        query = url.split('?', 1)[1]
        params = parse_params(query)
        self.assertEqual(params['action'], 'station')
        self.assertEqual(params['station'], 'track:123')
        self.assertEqual(params['name'], 'Мой трек')

    def test_leading_question_mark(self):
        self.assertEqual(parse_params('?action=play'), {'action': 'play'})

    def test_blank_values_kept(self):
        self.assertEqual(parse_params('q=&type=track'), {'q': '', 'type': 'track'})


if __name__ == '__main__':
    unittest.main()
