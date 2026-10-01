"""Contract statistics tests; synthetic numbers are unit fixtures only."""
import math
import unittest

from summarize import GROUP, stats, summarize_rows


class StatisticsTests(unittest.TestCase):
    def test_nearest_rank_even_median_and_sample_stddev(self):
        s = stats([1, 2, 3, 4])
        self.assertEqual(s['median'], 2.5)
        self.assertEqual(s['p95'], 4)
        self.assertAlmostEqual(s['sample_stddev'], math.sqrt(5/3))
        self.assertEqual(stats(list(range(1, 31)))['p95'], 29)
        self.assertIsNone(stats([3])['sample_stddev'])
        self.assertIsNone(stats([])['mean'])

    def test_failures_warmups_and_outliers(self):
        def row(value, success=True, phase='measured'):
            r = dict(zip(GROUP, ['baseline', 'tcp', 'cold', 'ingress-ifb', 'performance', 6, 1048576, 16384]))
            r.update(total_ms=value, success=success, phase=phase, error_code='' if success else 'timeout')
            return r
        values = [row(1), row(3), row(101), row(None, False), row(100000, phase='warmup')]
        result = summarize_rows(values, metrics=['total_ms'])[0]
        self.assertEqual((result['n_attempted'], result['n_success'], result['n_failed']), (4, 3, 1))
        self.assertEqual(result['failure_rate'], .25)
        self.assertEqual(result['n_timeout'], 1)
        self.assertEqual(result['mean'], 35)
        self.assertEqual(result['p95'], 101)
        all_fail = summarize_rows([row(None, False)], metrics=['total_ms'])[0]
        self.assertEqual(all_fail['failure_rate'], 1)
        self.assertIsNone(all_fail['median'])


if __name__ == '__main__':
    unittest.main()
