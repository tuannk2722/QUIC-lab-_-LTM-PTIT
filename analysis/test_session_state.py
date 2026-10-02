"""Session consistency fixtures only; no invented network measurements."""
import unittest
from validate import validate_session_state


class SessionStateTests(unittest.TestCase):
    def run_state(self, **changes):
        r = dict(run_id='unit', transport='quic', mode='early', attempted_0rtt=True,
                 tls_resumed=True, used_0rtt=False, early_rejected=True, fallback_count=1,
                 early_ready_ms=1, handshake_ms=2, elapsed_ms=4)
        return dict(r, **changes)

    def test_rejected_fallback_and_unknown_failure(self):
        validate_session_state(self.run_state(), [dict(attempt_index=1)])
        validate_session_state(self.run_state(used_0rtt=None, tls_resumed=None, fallback_count=0), [dict(attempt_index=0)])
        validate_session_state(self.run_state(mode='cold', attempted_0rtt=False, used_0rtt=None,
            tls_resumed=None, early_rejected=None, fallback_count=0, early_ready_ms=None), [dict(attempt_index=0)])

    def test_no_fabricated_acceptance_or_mixed_attempt(self):
        for changes, index in [({'used_0rtt':True},1), ({'early_rejected':False},1),
                               ({'attempted_0rtt':False},1), ({'mode':'resumed'},1), ({},0),
                               ({'handshake_ms':None},1), ({'early_ready_ms':5},1),
                               ({'handshake_ms':5},1),
                               ({'used_0rtt':True,'early_rejected':False,'fallback_count':0,'early_ready_ms':None},0),
                               ({'used_0rtt':True,'early_rejected':False,'fallback_count':0,'tls_resumed':False},0)]:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    validate_session_state(self.run_state(**changes), [dict(attempt_index=index)])


if __name__ == '__main__':
    unittest.main()
