import unittest

import _bootstrap  # noqa: F401

from ymkodi.updatecheck import version_tuple


class VersionTupleTest(unittest.TestCase):
    def test_numeric_order(self):
        self.assertLess(version_tuple('0.1.8'), version_tuple('0.1.9'))
        self.assertLess(version_tuple('0.1.9'), version_tuple('0.2.0'))
        self.assertLess(version_tuple('0.9.9'), version_tuple('0.10.0'))

    def test_v_prefix(self):
        self.assertEqual(version_tuple('v1.2.3'), (1, 2, 3))
        self.assertEqual(version_tuple('V1.2.3'), (1, 2, 3))

    def test_garbage(self):
        self.assertEqual(version_tuple(''), (0,))
        self.assertEqual(version_tuple(None), (0,))
        self.assertEqual(version_tuple('abc'), (0,))
        self.assertEqual(version_tuple('1.2.3-beta'), (1, 2, 3))

    def test_release_is_newer(self):
        # simulated check: release v0.1.9 vs installed 0.1.8
        self.assertGreater(version_tuple('0.1.9'), version_tuple('0.1.8'))


if __name__ == '__main__':
    unittest.main()
