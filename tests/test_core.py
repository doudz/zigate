'''
ZiGate responses Tests
-------------------------
'''

import unittest
import os
import tempfile
from zigate import core


class TestCore(unittest.TestCase):
    def setUp(self):
        self.zigate = core.ZiGate(auto_start=False)
        self.test_dir = tempfile.mkdtemp()

    def test_persistent(self):
        path = os.path.join(self.test_dir, 'test_zigate.json')
        backup_path = path + '.0'

        result = self.zigate.load_state(path)
        self.assertFalse(result)

        with open(path, 'w') as fp:
            fp.write('fake file - test')
        result = self.zigate.load_state(path)
        self.assertFalse(result)

        os.remove(path)

        self.zigate.save_state(path)
        self.assertTrue(os.path.exists(path))
        self.assertFalse(os.path.exists(backup_path))
        self.zigate.save_state(path)
        self.assertTrue(os.path.exists(backup_path))

        result = self.zigate.load_state(path)
        self.assertTrue(result)

        os.remove(path)
        os.remove(backup_path)


if __name__ == '__main__':
    unittest.main()
