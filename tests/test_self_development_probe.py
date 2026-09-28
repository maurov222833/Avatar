import unittest
from core.cognitive.self_development_probe import avatar_probe

class TestSelfDevelopmentProbe(unittest.TestCase):
    def test_avatar_probe(self):
        self.assertEqual(avatar_probe(), 'AVATAR_SELF_DEVELOPMENT_OK')

if __name__ == '__main__':
    unittest.main()
