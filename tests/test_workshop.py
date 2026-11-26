import unittest
from agent_workshop.booking import BookingStore, Concierge, run_slot_race
from agent_workshop.mr_review import ReviewSupervisor

class BookingTests(unittest.TestCase):
    def test_booking_confirmation(self):
        c = Concierge(BookingStore())
        offered = c.on_message('customer', 'Dr Rao Friday', 'id-1')
        self.assertEqual(offered.state, 'OFFERED')
        confirmed = c.on_message('customer', 'YES', 'id-2')
        self.assertEqual(confirmed.state, 'CONFIRMED')
        self.assertEqual(c.store.summary()['bookings'], 1)
    def test_repeated_sms_is_idempotent(self):
        c = Concierge(BookingStore())
        c.on_message('a', 'Dr Rao Friday', 'a1')
        x = c.on_message('a','YES','a2')
        y = c.on_message('a','YES','a2')
        self.assertEqual(x.reference, y.reference)
        self.assertEqual(c.store.summary()['bookings'], 1)
    def test_human_handoff(self):
        c = Concierge(BookingStore())
        result = c.on_message('a','please call me, human supervisor','a1')
        self.assertEqual(result.state, 'ESCALATED')
        self.assertEqual(c.store.summary()['escalations'], 1)
    def test_concurrent_confirmation_one_slot(self):
        result = run_slot_race(20)
        self.assertEqual(result['confirmed'], 1)
        self.assertEqual(result['conflicts'], 19)
        self.assertEqual(result['booking_rows'], 1)

class MRTests(unittest.TestCase):
    def test_block_high_security_finding(self):
        result = ReviewSupervisor().review('risky')
        self.assertEqual(result['decision'], 'BLOCK')
        self.assertEqual(len(result['findings']), 4)
    def test_clean_fixture(self):
        result = ReviewSupervisor().review('clean')
        self.assertEqual(result['decision'], 'STANDARD_REVIEW')
        self.assertEqual(result['findings'], [])

if __name__ == '__main__':
    unittest.main()
