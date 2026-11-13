import importlib.util
import json
import unittest
from pathlib import Path

path = Path(__file__).parents[1] / 'scripts' / 'events.py'
spec = importlib.util.spec_from_file_location('events', path)
if spec and path.exists():
    events = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(events)
else:
    events = None

class EventTests(unittest.TestCase):
    def test_valid_session(self):
        self.assertIsNotNone(events)
        self.assertEqual(events.parse_events([json.dumps({'sessionID': 's1'})], None), 's1')

    def test_conflicts_and_bad_json_fail(self):
        self.assertIsNotNone(events)
        for lines, expected in [(['not json'], None), ([json.dumps({'sessionID':'a'}), json.dumps({'sessionID':'b'})], None), ([json.dumps({'sessionID':'a'})], 'b'), ([], None), ([json.dumps({'type':'error','sessionID':'a'})], None)]:
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                events.parse_events(lines, expected)

if __name__ == '__main__':
    unittest.main()
