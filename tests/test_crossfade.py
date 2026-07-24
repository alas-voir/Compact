import unittest

from src.crossfade import crossfade_gains


class CrossfadeGainTests(unittest.TestCase):
    def test_endpoints_use_complementary_gains(self) -> None:
        self.assertEqual(crossfade_gains(0.0), (1.0, 0.0))
        self.assertEqual(crossfade_gains(1.0), (0.0, 1.0))

    def test_both_tracks_change_volume_during_transition(self) -> None:
        outgoing, incoming = crossfade_gains(0.25)
        self.assertAlmostEqual(outgoing, 0.75)
        self.assertAlmostEqual(incoming, 0.25)

        later_outgoing, later_incoming = crossfade_gains(0.75)
        self.assertLess(later_outgoing, outgoing)
        self.assertGreater(later_incoming, incoming)

    def test_progress_is_clamped(self) -> None:
        self.assertEqual(crossfade_gains(-1.0), (1.0, 0.0))
        self.assertEqual(crossfade_gains(2.0), (0.0, 1.0))


if __name__ == "__main__":
    unittest.main()
