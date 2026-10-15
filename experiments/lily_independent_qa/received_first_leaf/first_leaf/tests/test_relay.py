from pathlib import Path
import json
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from relay import init, transact, writer_lock
from first_leaf import canonical

class RelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.packet = init(self.d, 20000, 'scripted_test_not_hosted_model')
    def tearDown(self):
        self.tmp.cleanup()
    def req(self, action='k0', uid='one'):
        r = json.loads((self.d / 'packet.json').read_text())['request_template']
        r.update(action=action, request_id=uid)
        return canonical(r)
    def test_public_packet_has_no_hidden_fixture(self):
        p = json.loads((self.d / 'packet.json').read_text())
        for k in ['fixture', 'mapping_A', 'mapping_B', 'true_b', 'unit_noise', 'seed', 'body_schedule']:
            self.assertNotIn(k, json.dumps(p))
    def test_duplicate_survives_state_restore(self):
        raw = self.req()
        transact(self.d, raw)
        event = transact(self.d, raw)
        self.assertTrue(event['receipt']['duplicate'])
        self.assertEqual(json.loads((self.d / 'private_state.json').read_text())['tick'], 1)
    def test_stopped_does_not_advance(self):
        transact(self.d, self.req('stop'))
        event = transact(self.d, self.req('k0', 'later'))
        self.assertEqual(event['receipt']['reason'], 'stop_latched')
        self.assertEqual(json.loads((self.d / 'private_state.json').read_text())['tick'], 0)
    def test_bad_request_logged(self):
        event = transact(self.d, b'{bad')
        self.assertFalse(event['executed'])
        self.assertEqual(len((self.d / 'events.jsonl').read_text().splitlines()), 1)
    def test_full_episode_and_explicit_reset(self):
        for t in range(80):
            transact(self.d, self.req('k' + str(t % 4), str(t)))
        self.assertTrue(json.loads((self.d / 'packet.json').read_text())['episode_complete'])
        event = transact(self.d, advance=True)
        self.assertEqual(event['event'], 'operator_episode_reset')
        self.assertEqual(json.loads((self.d / 'private_state.json').read_text())['episode'], 1)
    def test_collision_lock_blocks_writer(self):
        with writer_lock(self.d):
            with self.assertRaises(RuntimeError):
                transact(self.d, self.req())
    def test_cannot_overwrite_session(self):
        with self.assertRaises(ValueError):
            init(self.d, 20000, 'wrong')

if __name__ == '__main__':
    unittest.main()
