from __future__ import division

import unittest

import numpy as np

import icarus.tools.cacheperf as cacheperf
import icarus.models as cache
import icarus.scenarios as scenarios
import icarus.tools.stats as stats


class TestNumericCacheHitRatio(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.n = 500
        cls.pdf = np.ones(cls.n) / cls.n

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_lru_cache(self):
        r = 0.1
        h = cacheperf.numeric_cache_hit_ratio(self.pdf, cache.LruCache(r * self.n))
        self.assertLess(np.abs(h - r), 0.01)

    def test_in_cache_lfu_cache(self):
        r = 0.1
        h = cacheperf.numeric_cache_hit_ratio(self.pdf, cache.InCacheLfuCache(r * self.n))
        self.assertLess(np.abs(h - r), 0.01)

    def test_fifo_cache(self):
        r = 0.1
        h = cacheperf.numeric_cache_hit_ratio(self.pdf, cache.FifoCache(r * self.n))
        self.assertLess(np.abs(h - r), 0.01)

    def test_rand_cache(self):
        r = 0.1
        h = cacheperf.numeric_cache_hit_ratio(self.pdf, cache.RandEvictionCache(r * self.n))
        self.assertLess(np.abs(h - r), 0.01)


class TestLaoutarisPerContentCacheHitRatio(unittest.TestCase):

    def test_3rd_order_positive_disc(self):
        H = cacheperf.laoutaris_per_content_cache_hit_ratio(0.8, 1000, 100, 3)
        prev_h = 1
        for h in H:
            self.assertGreaterEqual(h, 0)
            self.assertLessEqual(h, 1)
            self.assertLessEqual(h, prev_h)
            prev_h = h

    def test_3rd_order_negative_disc(self):
        H = cacheperf.laoutaris_per_content_cache_hit_ratio(0.7, 1000, 100, 3)
        prev_h = 1
        for h in H:
            self.assertGreaterEqual(h, 0)
            self.assertLessEqual(h, 1)
            self.assertLessEqual(h, prev_h)
            prev_h = h


class TestFaginApproximation(unittest.TestCase):

    # Numerically evaluated cache hit ratio for alpha=0.8, n=100 and c=40 is ~ 0.64
    # Fagin characteristic time is ~ 71.89

    @classmethod
    def setUpClass(cls):
        cls.pdf = stats.TruncatedZipfDist(alpha=0.8, n=100).pdf
        cls.cache_size = 40

    def test_fagin_characteristic_time(self):
        t = cacheperf.fagin_characteristic_time(self.pdf, self.cache_size)
        self.assertGreaterEqual(t, self.cache_size)
        self.assertGreaterEqual(t, 71.8)
        self.assertLessEqual(t, 72)

    def test_fagin_cache_hit_ratio(self):
        h = cacheperf.fagin_cache_hit_ratio(self.pdf, self.cache_size)
        self.assertGreaterEqual(h, 0.63)
        self.assertLessEqual(h, 0.66)

    def test_fagin_per_content_cache_hit_ratio(self):
        H = cacheperf.fagin_per_content_cache_hit_ratio(self.pdf, self.cache_size)
        prev_h = 1
        for h in H:
            self.assertGreaterEqual(h, 0)
            self.assertLessEqual(h, 1)
            self.assertLessEqual(h, prev_h)
            prev_h = h


class TestCheApproximation(unittest.TestCase):

    # Numerically evaluated cache hit ratio for alpha=0.8, n=100 and c=40 is ~ 0.64

    @classmethod
    def setUpClass(cls):
        cls.pdf = stats.TruncatedZipfDist(alpha=0.8, n=100).pdf
        cls.cache_size = 40

    def test_che_characteristic_time(self):
        T = cacheperf.che_characteristic_time(self.pdf, self.cache_size)
        prev_t = np.infty
        for t in T:
            self.assertGreaterEqual(t, self.cache_size)
            self.assertLessEqual(t, prev_t)
            prev_t = t

    def test_che_characteristic_time_simplified(self):
        t = cacheperf.che_characteristic_time_simplified(self.pdf, self.cache_size)
        self.assertGreaterEqual(t, self.cache_size)
        self.assertGreaterEqual(t, 72.1)
        self.assertLessEqual(t, 72.3)

    def test_che_characteristic_time_generalized(self):
        t = cacheperf.che_characteristic_time_generalized(self.pdf, self.cache_size, "LRU")
        self.assertGreaterEqual(t, self.cache_size)
        self.assertGreaterEqual(t, 72.1)
        self.assertLessEqual(t, 72.3)

    def test_che_cache_hit_ratio(self):
        h = cacheperf.che_cache_hit_ratio(self.pdf, self.cache_size)
        self.assertGreaterEqual(h, 0.63)
        self.assertLessEqual(h, 0.66)

    def test_che_cache_hit_ratio_simplified(self):
        h = cacheperf.che_cache_hit_ratio_simplified(self.pdf, self.cache_size)
        self.assertGreaterEqual(h, 0.63)
        self.assertLessEqual(h, 0.66)

    def test_che_cache_hit_ratio_generalized(self):
        h = cacheperf.che_cache_hit_ratio_generalized(self.pdf, self.cache_size, "LRU")
        self.assertGreaterEqual(h, 0.63)
        self.assertLessEqual(h, 0.66)

    def test_che_per_content_cache_hit_ratio(self):
        H = cacheperf.che_per_content_cache_hit_ratio(self.pdf, self.cache_size)
        prev_h = 1
        for h in H:
            self.assertGreaterEqual(h, 0)
            self.assertLessEqual(h, 1)
            self.assertLessEqual(h, prev_h)
            prev_h = h

    def test_che_per_content_cache_hit_ratio_simplified(self):
        H = cacheperf.che_per_content_cache_hit_ratio_simplified(self.pdf, self.cache_size)
        prev_h = 1
        for h in H:
            self.assertGreaterEqual(h, 0)
            self.assertLessEqual(h, 1)
            self.assertLessEqual(h, prev_h)
            prev_h = h

    def test_che_per_content_cache_hit_ratio_generalized(self):
        H = cacheperf.che_per_content_cache_hit_ratio_generalized(self.pdf, self.cache_size, "LRU")
        prev_h = 1
        for h in H:
            self.assertGreaterEqual(h, 0)
            self.assertLessEqual(h, 1)
            self.assertLessEqual(h, prev_h)
            prev_h = h


class TestLaoutarisCacheHitRatio(unittest.TestCase):

    def test_3rd_order_positive_disc(self):
        h = cacheperf.laoutaris_cache_hit_ratio(0.8, 1000, 100, 3)
        self.assertGreaterEqual(h, 0)

    def test_3rd_order_negative_disc(self):
        h = cacheperf.laoutaris_cache_hit_ratio(0.7, 1000, 100, 3)
        self.assertGreaterEqual(h, 0)


class TestOptimalCacheHitRatio(unittest.TestCase):

    def test_unsorted_pdf(self):
        h = cacheperf.optimal_cache_hit_ratio([0.1, 0.5, 0.4], 2)
        self.assertAlmostEqual(0.9, h)

class TestHashrouting(unittest.TestCase):

    def test_arbitrary(self):
        topologies = [
            1221,
            1239,
            1755,
            3257,
            3967,
            6461,
        ]
        n_contents = 10000
        network_cache = 0.1
        hit_ratio = 0.2

        results = {
            1221: 104.43627218934938,
            1239: 129.9188933590089,
            3257: 102.65934570425449,
            1755: 94.2634958382883,
            6461: 168.74678558156853,
            3967: 132.65163549797435
        }

        for asn in topologies:
            # Set up topology
            topo = scenarios.topology_rocketfuel_latency(asn, source_ratio=0.1)
            scenarios.uniform_cache_placement(topo, n_contents*network_cache)
            sources = topo.sources()
            receivers = topo.receivers()
            req_rates = {v: 1/len(receivers) for v in receivers}
            source_content_ratio = {v: 1/len(sources) for v in sources}
            # Run experiment and validate results
            latency = cacheperf.hashrouting_model(topo, 'SYMM', hit_ratio, source_content_ratio, req_rates)
            self.assertAlmostEqual(results[asn], latency)

    def test_mesh(self):
        l = cacheperf.hashrouting_model_mesh(10, 5, 0.1, 1, 1.5)
        self.assertAlmostEqual(5.4, l)

    def test_ring(self):
        l = cacheperf.hashrouting_model_ring(2, 0.1, 2, 3)
        self.assertAlmostEqual(9.2, l)
        l = cacheperf.hashrouting_model_ring(5, 0.1, 2, 3)
        self.assertAlmostEqual(14.52, l)
        l = cacheperf.hashrouting_model_ring(8, 0.1, 2, 3)
        self.assertAlmostEqual(20.6, l)
