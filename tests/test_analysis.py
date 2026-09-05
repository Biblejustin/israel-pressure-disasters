import random
import unittest
from datetime import date, timedelta
from unittest.mock import patch
import analyze as a

class AnalysisTests(unittest.TestCase):
    def test_tail_deficit(self):
        start,end=date(2020,1,1),date(2020,1,31)
        events=[start]
        onsets={start+timedelta(days=i) for i in range(1,31)}
        with patch.object(a,'N_PERM',4000):
            _,lower=a.perm_p(events,onsets,0,0,start,end,random.Random(7),'shift','lower')
            _,upper=a.perm_p(events,onsets,0,0,start,end,random.Random(7),'shift','upper')
        self.assertLess(lower,.06)
        self.assertEqual(upper,1)

    def test_response_window_clipping(self):
        start,end=date(2024,1,1),date(2024,12,31)
        events=[start,start+timedelta(days=7),end-timedelta(days=7),end]
        self.assertEqual(a.eligible_events(events,start,end,-7,7),events[1:3])
        self.assertEqual(a.eligible_events(events,start,end,0,7),events[:3])

    def test_year_shuffle_includes_last_year(self):
        start,end=date(2024,1,1),date(2024,12,31)
        with patch.object(a,'N_PERM',10):
            observed,p=a.perm_p([date(2024,6,1)],{date(2024,6,2)},0,7,start,end,random.Random(1),'yshuf')
        self.assertEqual((observed,p),(1,1))

    def test_baseline_matches_admissible_dates(self):
        start,end=date(2024,1,1),date(2024,1,10)
        self.assertAlmostEqual(a.base_rate({end},0,3,start,end),1/7)

    def test_common_historical_scope(self):
        for _,onsets,start,end in a.historical_datasets():
            self.assertEqual(end,date(2024,12,31))
            self.assertTrue(all(start<=x<=end for x in onsets))

if __name__=='__main__': unittest.main()
