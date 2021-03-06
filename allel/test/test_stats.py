# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division


import unittest


import numpy as np
from nose.tools import assert_raises, eq_ as eq
from allel.test.tools import assert_array_equal as aeq, assert_array_close, \
    assert_array_nanclose


from allel.util import ignore_invalid
from allel.model.ndarray import GenotypeArray, HaplotypeArray, SortedIndex
import allel.stats


class TestWindowUtilities(unittest.TestCase):

    def test_moving_statistic(self):
        f = allel.stats.moving_statistic

        values = [2, 5, 8, 16]
        expect = [7, 24]
        actual = f(values, statistic=np.sum, size=2)
        aeq(expect, actual)

        values = [2, 5, 8, 16]
        expect = [7, 13, 24]
        actual = f(values, statistic=np.sum, size=2, step=1)
        aeq(expect, actual)

    def test_windowed_statistic(self):
        f = allel.stats.windowed_statistic
        pos = [1, 12, 15, 27]

        # boolean array, all true
        b = [True, True, True, True]
        expected_nnz = [1, 2, 1]
        expected_windows = [[1, 10], [11, 20], [21, 27]]
        expected_counts = [1, 2, 1]
        actual_nnz, actual_windows, actual_counts = \
            f(pos, b, np.count_nonzero, 10)
        aeq(expected_nnz, actual_nnz)
        aeq(expected_windows, actual_windows)
        aeq(expected_counts, actual_counts)

        # boolean array, not all true
        b = [False, True, False, True]
        expected_nnz = [0, 1, 1]
        expected_windows = [[1, 10], [11, 20], [21, 27]]
        expected_counts = [1, 2, 1]
        actual_nnz, actual_windows, actual_counts = \
            f(pos, b, np.count_nonzero, 10)
        aeq(expected_windows, actual_windows)
        aeq(expected_nnz, actual_nnz)
        aeq(expected_counts, actual_counts)

        # explicit start and stop
        b = [False, True, False, True]
        expected_nnz = [1, 0, 1]
        expected_windows = [[5, 14], [15, 24], [25, 29]]
        expected_counts = [1, 1, 1]
        actual_nnz, actual_windows, actual_counts = \
            f(pos, b, np.count_nonzero, 10, start=5, stop=29)
        aeq(expected_windows, actual_windows)
        aeq(expected_nnz, actual_nnz)
        aeq(expected_counts, actual_counts)

        # boolean array, bad length
        b = [False, True, False]
        with assert_raises(ValueError):
            f(pos, b, np.count_nonzero, 10)

        # 2D, 4 variants, 2 samples
        b = [[True, False],
             [True, True],
             [True, False],
             [True, True]]
        expected_nnz = [[1, 0],
                        [2, 1],
                        [1, 1]]
        expected_windows = [[1, 10], [11, 20], [21, 27]]
        expected_counts = [1, 2, 1]
        actual_nnz, actual_windows, actual_counts = \
            f(pos, b, statistic=lambda x: np.sum(x, axis=0), size=10)
        aeq(expected_nnz, actual_nnz)
        aeq(expected_windows, actual_windows)
        aeq(expected_counts, actual_counts)

    def test_per_base(self):
        pos = [1, 12, 15, 27]

        # boolean array, all true
        b = [True, True, True, True]
        # N.B., final bin includes right edge
        expected_nnz = [1, 2, 1]
        expected_windows = [[1, 10], [11, 20], [21, 27]]
        expected_counts = [1, 2, 1]
        expected_densities = [1/10, 2/10, 1/7]
        expected_n_bases = [10, 10, 7]
        nnz, windows, counts = allel.stats.windowed_statistic(
            pos, b, statistic=np.count_nonzero, size=10, start=1
        )
        densities, n_bases = allel.stats.per_base(nnz, windows)
        aeq(expected_nnz, nnz)
        aeq(expected_windows, windows)
        aeq(expected_counts, counts)
        aeq(expected_densities, densities)
        aeq(expected_n_bases, n_bases)

        # boolean array, not all true
        b = [False, True, False, True]
        expected_densities = [0/10, 1/10, 1/7]
        expected_n_bases = [10, 10, 7]
        nnz, windows, counts = allel.stats.windowed_statistic(
            pos, b, statistic=np.count_nonzero, size=10, start=1
        )
        densities, n_bases = allel.stats.per_base(nnz, windows)
        aeq(expected_densities, densities)
        aeq(expected_n_bases, n_bases)

        # 2D, 4 variants, 2 samples
        b = [[True, False],
             [True, True],
             [True, False],
             [True, True]]
        expected_densities = [[1/10, 0/10],
                              [2/10, 1/10],
                              [1/7, 1/7]]
        expected_n_bases = [10, 10, 7]
        nnz, windows, counts = allel.stats.windowed_statistic(
            pos, b, statistic=lambda x: np.sum(x, axis=0), size=10, start=1
        )
        densities, n_bases = allel.stats.per_base(nnz, windows)
        aeq(expected_densities, densities)
        aeq(expected_n_bases, n_bases)

        # include is_accessible array option
        is_accessible = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                  1, 1, 1, 1, 0, 0, 1, 1, 0, 0,
                                  1, 1, 1, 1, 1, 1, 1, 1, 1, 1], dtype=bool)
        b = [False, True, False, True]
        expected_densities = [-1, 1/6, 1/7]
        expected_n_bases = [0, 6, 7]
        nnz, windows, counts = allel.stats.windowed_statistic(
            pos, b, statistic=np.count_nonzero, size=10, start=1
        )
        densities, n_bases = allel.stats.per_base(nnz, windows,
                                                  is_accessible=is_accessible,
                                                  fill=-1)
        aeq(expected_densities, densities)
        aeq(expected_n_bases, n_bases)


class TestDiversityDivergence(unittest.TestCase):

    def test_mean_pairwise_diversity(self):

        # start with simplest case, two haplotypes, one pairwise comparison
        h = HaplotypeArray([[0, 0],
                            [1, 1],
                            [0, 1],
                            [1, 2],
                            [0, -1],
                            [-1, -1]])
        ac = h.count_alleles()
        expect = [0, 0, 1, 1, -1, -1]
        actual = allel.stats.mean_pairwise_difference(ac, fill=-1)
        aeq(expect, actual)

        # four haplotypes, 6 pairwise comparison
        h = HaplotypeArray([[0, 0, 0, 0],
                            [0, 0, 0, 1],
                            [0, 0, 1, 1],
                            [0, 1, 1, 1],
                            [1, 1, 1, 1],
                            [0, 0, 1, 2],
                            [0, 1, 1, 2],
                            [0, 1, -1, -1],
                            [-1, -1, -1, -1]])
        ac = h.count_alleles()
        expect = [0, 3/6, 4/6, 3/6, 0, 5/6, 5/6, 1, -1]
        actual = allel.stats.mean_pairwise_difference(ac, fill=-1)
        assert_array_close(expect, actual)

    def test_windowed_diversity(self):

        # four haplotypes, 6 pairwise comparison
        h = HaplotypeArray([[0, 0, 0, 0],
                            [0, 0, 0, 1],
                            [0, 0, 1, 1],
                            [0, 1, 1, 1],
                            [1, 1, 1, 1],
                            [0, 0, 1, 2],
                            [0, 1, 1, 2],
                            [0, 1, -1, -1],
                            [-1, -1, -1, -1]])
        ac = h.count_alleles()
        # mean pairwise diversity
        # expect = [0, 3/6, 4/6, 3/6, 0, 5/6, 5/6, 1, -1]
        pos = SortedIndex([2, 4, 7, 14, 15, 18, 19, 25, 27])
        expect = [(7/6)/10, (13/6)/10, 1/11]
        actual, _, _, _ = allel.stats.windowed_diversity(pos, ac, size=10,
                                                         start=1,
                                                         stop=31)
        assert_array_close(expect, actual)

    def test_mean_pairwise_divergence(self):

        # simplest case, two haplotypes in each population
        h = HaplotypeArray([[0, 0, 0, 0],
                            [0, 0, 0, 1],
                            [0, 0, 1, 1],
                            [0, 1, 1, 1],
                            [1, 1, 1, 1],
                            [0, 0, 1, 2],
                            [0, 1, 1, 2],
                            [0, 1, -1, -1],
                            [-1, -1, -1, -1]])
        h1 = h.take([0, 1], axis=1)
        h2 = h.take([2, 3], axis=1)
        ac1 = h1.count_alleles()
        ac2 = h2.count_alleles()

        expect = [0/4, 2/4, 4/4, 2/4, 0/4, 4/4, 3/4, -1, -1]
        actual = allel.stats.mean_pairwise_difference_between(ac1, ac2,
                                                              fill=-1)
        aeq(expect, actual)

    def test_windowed_divergence(self):

        # simplest case, two haplotypes in each population
        h = HaplotypeArray([[0, 0, 0, 0],
                            [0, 0, 0, 1],
                            [0, 0, 1, 1],
                            [0, 1, 1, 1],
                            [1, 1, 1, 1],
                            [0, 0, 1, 2],
                            [0, 1, 1, 2],
                            [0, 1, -1, -1],
                            [-1, -1, -1, -1]])
        h1 = h.take([0, 1], axis=1)
        h2 = h.take([2, 3], axis=1)
        ac1 = h1.count_alleles()
        ac2 = h2.count_alleles()
        # mean pairwise divergence
        # expect = [0/4, 2/4, 4/4, 2/4, 0/4, 4/4, 3/4, -1, -1]
        pos = SortedIndex([2, 4, 7, 14, 15, 18, 19, 25, 27])
        expect = [(6/4)/10, (9/4)/10, 0/11]
        actual, _, _, _ = allel.stats.windowed_divergence(
            pos, ac1, ac2, size=10, start=1, stop=31
        )
        assert_array_close(expect, actual)


class TestHardyWeinberg(unittest.TestCase):

    def test_heterozygosity_observed(self):

        # diploid
        g = GenotypeArray([[[0, 0], [0, 0]],
                           [[1, 1], [1, 1]],
                           [[1, 1], [2, 2]],
                           [[0, 0], [0, 1]],
                           [[0, 0], [0, 2]],
                           [[1, 1], [1, 2]],
                           [[0, 1], [0, 1]],
                           [[0, 1], [1, 2]],
                           [[0, 0], [-1, -1]],
                           [[0, 1], [-1, -1]],
                           [[-1, -1], [-1, -1]]], dtype='i1')
        expect = [0, 0, 0, .5, .5, .5, 1, 1, 0, 1, -1]
        actual = allel.stats.heterozygosity_observed(g, fill=-1)
        aeq(expect, actual)

        # polyploid
        g = GenotypeArray([[[0, 0, 0], [0, 0, 0]],
                           [[1, 1, 1], [1, 1, 1]],
                           [[1, 1, 1], [2, 2, 2]],
                           [[0, 0, 0], [0, 0, 1]],
                           [[0, 0, 0], [0, 0, 2]],
                           [[1, 1, 1], [0, 1, 2]],
                           [[0, 0, 1], [0, 1, 1]],
                           [[0, 1, 1], [0, 1, 2]],
                           [[0, 0, 0], [-1, -1, -1]],
                           [[0, 0, 1], [-1, -1, -1]],
                           [[-1, -1, -1], [-1, -1, -1]]], dtype='i1')
        expect = [0, 0, 0, .5, .5, .5, 1, 1, 0, 1, -1]
        actual = allel.stats.heterozygosity_observed(g, fill=-1)
        aeq(expect, actual)

    def test_heterozygosity_expected(self):

        def refimpl(af, ploidy, fill=0):
            """Limited reference implementation for testing purposes."""

            # check allele frequencies sum to 1
            af_sum = np.sum(af, axis=1)

            # assume three alleles
            p = af[:, 0]
            q = af[:, 1]
            r = af[:, 2]

            out = 1 - p**ploidy - q**ploidy - r**ploidy
            with ignore_invalid():
                out[(af_sum < 1) | np.isnan(af_sum)] = fill

            return out

        # diploid
        g = GenotypeArray([[[0, 0], [0, 0]],
                           [[1, 1], [1, 1]],
                           [[1, 1], [2, 2]],
                           [[0, 0], [0, 1]],
                           [[0, 0], [0, 2]],
                           [[1, 1], [1, 2]],
                           [[0, 1], [0, 1]],
                           [[0, 1], [1, 2]],
                           [[0, 0], [-1, -1]],
                           [[0, 1], [-1, -1]],
                           [[-1, -1], [-1, -1]]], dtype='i1')
        expect1 = [0, 0, 0.5, .375, .375, .375, .5, .625, 0, .5, -1]
        af = g.count_alleles().to_frequencies()
        expect2 = refimpl(af, ploidy=g.ploidy, fill=-1)
        actual = allel.stats.heterozygosity_expected(af, ploidy=g.ploidy,
                                                     fill=-1)
        assert_array_close(expect1, actual)
        assert_array_close(expect2, actual)
        expect3 = [0, 0, 0.5, .375, .375, .375, .5, .625, 0, .5, 0]
        actual = allel.stats.heterozygosity_expected(af, ploidy=g.ploidy,
                                                     fill=0)
        assert_array_close(expect3, actual)

        # polyploid
        g = GenotypeArray([[[0, 0, 0], [0, 0, 0]],
                           [[1, 1, 1], [1, 1, 1]],
                           [[1, 1, 1], [2, 2, 2]],
                           [[0, 0, 0], [0, 0, 1]],
                           [[0, 0, 0], [0, 0, 2]],
                           [[1, 1, 1], [0, 1, 2]],
                           [[0, 0, 1], [0, 1, 1]],
                           [[0, 1, 1], [0, 1, 2]],
                           [[0, 0, 0], [-1, -1, -1]],
                           [[0, 0, 1], [-1, -1, -1]],
                           [[-1, -1, -1], [-1, -1, -1]]], dtype='i1')
        af = g.count_alleles().to_frequencies()
        expect = refimpl(af, ploidy=g.ploidy, fill=-1)
        actual = allel.stats.heterozygosity_expected(af, ploidy=g.ploidy,
                                                     fill=-1)
        assert_array_close(expect, actual)

    def test_inbreeding_coefficient(self):

        # diploid
        g = GenotypeArray([[[0, 0], [0, 0]],
                           [[1, 1], [1, 1]],
                           [[1, 1], [2, 2]],
                           [[0, 0], [0, 1]],
                           [[0, 0], [0, 2]],
                           [[1, 1], [1, 2]],
                           [[0, 1], [0, 1]],
                           [[0, 1], [1, 2]],
                           [[0, 0], [-1, -1]],
                           [[0, 1], [-1, -1]],
                           [[-1, -1], [-1, -1]]], dtype='i1')
        # ho = np.array([0, 0, 0, .5, .5, .5, 1, 1, 0, 1, -1])
        # he = np.array([0, 0, 0.5, .375, .375, .375, .5, .625, 0, .5, -1])
        # expect = 1 - (ho/he)
        expect = [-1, -1, 1-0, 1-(.5/.375), 1-(.5/.375), 1-(.5/.375),
                  1-(1/.5), 1-(1/.625), -1, 1-(1/.5), -1]
        actual = allel.stats.inbreeding_coefficient(g, fill=-1)
        assert_array_close(expect, actual)


class TestDistance(unittest.TestCase):

    def test_pdist(self):
        h = HaplotypeArray([[0, 0, 0, 0],
                            [0, 0, 0, 1],
                            [0, 0, 1, 1],
                            [0, 1, 1, 1],
                            [1, 1, 1, 1],
                            [0, 0, 1, 2],
                            [0, 1, 1, 2],
                            [0, 1, -1, -1],
                            [-1, -1, -1, -1]])
        import scipy.spatial
        d1 = scipy.spatial.distance.pdist(h.T, 'hamming')
        import allel.stats.distance
        d2 = allel.stats.distance.pdist(h, 'hamming')
        aeq(d1, d2)

    def test_pairwise_distance_multidim(self):
        g = GenotypeArray([[[0, 0], [0, 0]],
                           [[1, 1], [1, 1]],
                           [[1, 1], [2, 2]],
                           [[0, 0], [0, 1]],
                           [[0, 0], [0, 2]],
                           [[1, 1], [1, 2]],
                           [[0, 1], [0, 1]],
                           [[0, 1], [1, 2]],
                           [[0, 0], [-1, -1]],
                           [[0, 1], [-1, -1]],
                           [[-1, -1], [-1, -1]]], dtype='i1')
        gac = g.to_allele_counts()

        def metric(ac1, ac2):
            mpd = allel.stats.mean_pairwise_difference_between(ac1, ac2,
                                                               fill=0)
            return mpd.sum()

        expect = [
            allel.stats.mean_pairwise_difference_between(gac[:, 0], gac[:, 1],
                                                         fill=0).sum()]
        actual = allel.stats.pairwise_distance(gac, metric)
        aeq(expect, actual)


class TestLinkageDisequilibrium(unittest.TestCase):

    def test_rogers_huff_r(self):

        gn = [[0, 1, 2],
              [0, 1, 2]]
        expect = 1.
        actual = allel.stats.rogers_huff_r(gn)
        eq(expect, actual)

        gn = [[0, 1, 2],
              [2, 1, 0]]
        expect = -1.
        actual = allel.stats.rogers_huff_r(gn)
        eq(expect, actual)

        gn = [[0, 0, 0],
              [1, 1, 1]]
        actual = allel.stats.rogers_huff_r(gn)
        assert np.isnan(actual)

        gn = [[0, 1, 0, 1],
              [0, 1, 1, 0]]
        expect = 0
        actual = allel.stats.rogers_huff_r(gn)
        eq(expect, actual)

        gn = [[0, 1, 2, -1],
              [0, 1, 2, 2]]
        expect = 1.
        actual = allel.stats.rogers_huff_r(gn)
        eq(expect, actual)

        gn = [[0, 1, 2, 2],
              [0, 1, 2, -1]]
        expect = 1.
        actual = allel.stats.rogers_huff_r(gn)
        eq(expect, actual)

        gn = [[0, 1, 2],
              [0, 1, -1]]
        expect = 1.
        actual = allel.stats.rogers_huff_r(gn)
        eq(expect, actual)

        gn = [[0, 2],
              [2, 0],
              [0, 1]]
        expect = [-1, 1, -1]
        actual = allel.stats.rogers_huff_r(gn)
        assert_array_close(expect, actual)

        gn = [[0, 2, 0],
              [0, 2, 0],
              [2, 0, 2],
              [0, 2, -1]]
        expect = [1, -1, 1, -1, 1, -1]
        actual = allel.stats.rogers_huff_r(gn)
        assert_array_close(expect, actual)

    def test_rogers_huff_r_between(self):

        gna = [[0, 1, 2]]
        gnb = [[0, 1, 2]]
        expect = 1.
        actual = allel.stats.rogers_huff_r_between(gna, gnb)
        eq(expect, actual)

        gna = [[0, 1, 2]]
        gnb = [[2, 1, 0]]
        expect = -1.
        actual = allel.stats.rogers_huff_r_between(gna, gnb)
        eq(expect, actual)

        gna = [[0, 0, 0]]
        gnb = [[1, 1, 1]]
        actual = allel.stats.rogers_huff_r_between(gna, gnb)
        assert np.isnan(actual)

    def test_locate_unlinked(self):

        gn = [[0, 1, 2],
              [0, 1, 2]]
        expect = [True, False]
        actual = allel.stats.locate_unlinked(gn, size=2, step=2, threshold=.5)
        aeq(expect, actual)

        gn = [[0, 1, 1, 2],
              [0, 1, 1, 2],
              [1, 1, 0, 2],
              [1, 1, 0, 2]]
        actual = allel.stats.locate_unlinked(gn, size=2, step=1, threshold=.5)
        expect = [True, False, True, False]
        aeq(expect, actual)

        gn = [[0, 1, 1, 2],
              [0, 1, 1, 2],
              [0, 1, 1, 2],
              [1, 1, 0, 2],
              [1, 1, 0, 2]]
        actual = allel.stats.locate_unlinked(gn, size=2, step=1, threshold=.5)
        expect = [True, False, True, True, False]
        aeq(expect, actual)
        actual = allel.stats.locate_unlinked(gn, size=3, step=1, threshold=.5)
        expect = [True, False, False, True, False]
        aeq(expect, actual)

        # test with bcolz carray
        import bcolz
        gnz = bcolz.carray(gn, chunklen=2)
        actual = allel.stats.locate_unlinked(gnz, size=2, step=1,
                                             threshold=.5, chunked=True,
                                             blen=2)
        expect = [True, False, True, True, False]
        aeq(expect, actual)


class TestAdmixture(unittest.TestCase):

    def test_patterson_f2(self):
        aca = [[0, 2],
               [2, 0],
               [1, 1],
               [0, 0]]
        acb = [[0, 2],
               [0, 2],
               [0, 2],
               [0, 2]]
        expect = [0., 1., 0., np.nan]
        actual = allel.stats.patterson_f2(aca, acb)
        assert_array_nanclose(expect, actual)

    def test_patterson_f3(self):
        aca = [[0, 2],
               [2, 0],
               [0, 2],
               [0, 2],
               [0, 0]]
        acb = [[2, 0],
               [0, 2],
               [0, 2],
               [0, 2],
               [0, 2]]
        acc = [[1, 1],
               [1, 1],
               [0, 2],
               [2, 0],
               [1, 1]]
        expect_f3 = [-.5, -.5, 0., 1., np.nan]
        actual_f3, actual_hzc = allel.stats.patterson_f3(acc, aca, acb)
        assert_array_nanclose(expect_f3, actual_f3)
        expect_hzc = [1., 1., 0., 0., 1.]
        assert_array_nanclose(expect_hzc, actual_hzc)

    def test_patterson_d(self):
        aca = [[0, 2],
               [2, 0],
               [2, 0],
               [1, 1],
               [0, 0]]
        acb = [[0, 2],
               [0, 2],
               [0, 2],
               [1, 1],
               [0, 2]]
        acc = [[2, 0],
               [2, 0],
               [0, 2],
               [1, 1],
               [0, 2]]
        acd = [[2, 0],
               [0, 2],
               [2, 0],
               [1, 1],
               [0, 2]]
        num, den = allel.stats.patterson_d(aca, acb, acc, acd)
        expect_num = [0., 1., -1., 0., np.nan]
        expect_den = [0., 1., 1., 0.25, np.nan]
        assert_array_nanclose(expect_num, num)
        assert_array_nanclose(expect_den, den)


class TestSF(unittest.TestCase):

    def test_sfs(self):
        dac = [0, 1, 2, 1]
        expect = [1, 2, 1]
        actual = allel.stats.sfs(dac)
        aeq(expect, actual)

    def test_sfs_folded(self):
        ac = [[0, 3], [1, 2], [2, 1]]
        expect = [1, 2]
        actual = allel.stats.sfs_folded(ac)
        aeq(expect, actual)

    def test_sfs_scaled(self):
        dac = [0, 1, 2, 1]
        expect = [0, 2, 2]
        actual = allel.stats.sfs_scaled(dac)
        aeq(expect, actual)


class TestSelection(unittest.TestCase):

    def test_ssl01_scan_int8(self):
        from allel.opt.stats import nsl01_scan_int8

        h = np.array([[0, 0, 0, 1, 1, 1],
                      [0, 0, 0, 1, 1, 1],
                      [0, 0, 0, 1, 1, 1],
                      [0, 0, 0, 1, 1, 1]], dtype='i1')
        nsl0, nsl1 = nsl01_scan_int8(h)
        expect_nsl0 = [1, 2, 3, 4]
        assert_array_nanclose(expect_nsl0, nsl0)
        expect_nsl1 = [1, 2, 3, 4]
        assert_array_nanclose(expect_nsl1, nsl1)

        h = np.array([[0, 0, 0, 1],
                      [0, 0, 1, 0],
                      [0, 1, 0, 0],
                      [1, 0, 0, 0]], dtype='i1')
        nsl0, nsl1 = nsl01_scan_int8(h)
        expect_nsl0 = [1, 4/3, 4/3, 4/3]
        assert_array_nanclose(expect_nsl0, nsl0)
        expect_nsl1 = [np.nan, np.nan, np.nan, np.nan]
        assert_array_nanclose(expect_nsl1, nsl1)

        h = np.array([[0, 0, 1],
                      [0, 1, 1],
                      [1, 1, 0],
                      [1, 0, 0]], dtype='i1')
        nsl0, nsl1 = nsl01_scan_int8(h)
        expect_nsl0 = [1, np.nan, np.nan, 1]
        assert_array_nanclose(expect_nsl0, nsl0)
        expect_nsl1 = [np.nan, 1, 1, np.nan]
        assert_array_nanclose(expect_nsl1, nsl1)

    def test_ihh01_scan_int8(self):
        from allel.opt.stats import ihh01_scan_int8
        pos = [10, 20, 30, 40]

        # case 1
        h = np.array([[0, 0, 1],
                      [0, 1, 1],
                      [1, 1, 0],
                      [1, 0, 0]], dtype='i1')

        ihh0, ihh1 = ihh01_scan_int8(h, pos, min_ehh=0.05)
        expect_ihh0 = [np.nan, np.nan, np.nan, 0]
        assert_array_nanclose(expect_ihh0, ihh0)
        expect_ihh1 = [np.nan, np.nan, 0, np.nan]
        assert_array_nanclose(expect_ihh1, ihh1)

        ihh0, ihh1 = ihh01_scan_int8(h, pos, min_ehh=None)
        expect_ihh0 = [0, np.nan, np.nan, 0]
        assert_array_nanclose(expect_ihh0, ihh0)
        expect_ihh1 = [np.nan, 0, 0, np.nan]
        assert_array_nanclose(expect_ihh1, ihh1)

        # case 2
        h = np.array([[0, 0, 0, 1],
                      [0, 0, 1, 0],
                      [0, 1, 0, 0],
                      [1, 0, 0, 0]], dtype='i1')

        ihh0, ihh1 = ihh01_scan_int8(h, pos, min_ehh=0.05)
        expect_ihh0 = [np.nan, np.nan, np.nan, 10*2/3]
        assert_array_nanclose(expect_ihh0, ihh0)
        expect_ihh1 = [np.nan, np.nan, np.nan, np.nan]
        assert_array_nanclose(expect_ihh1, ihh1)

        ihh0, ihh1 = ihh01_scan_int8(h, pos, min_ehh=None)
        expect_ihh0 = [0, 10*2/3, 10*2/3, 10*2/3]
        assert_array_nanclose(expect_ihh0, ihh0)
        expect_ihh1 = [np.nan, np.nan, np.nan, np.nan]
        assert_array_nanclose(expect_ihh1, ihh1)

        # case 3
        h = np.array([[0, 0, 0, 1, 1, 1],
                      [0, 0, 0, 1, 1, 1],
                      [0, 0, 0, 1, 1, 1],
                      [0, 0, 0, 1, 1, 1]], dtype='i1')

        ihh0, ihh1 = ihh01_scan_int8(h, pos, min_ehh=0.05)
        expect_ihh0 = [np.nan, np.nan, np.nan, np.nan]
        assert_array_nanclose(expect_ihh0, ihh0)
        expect_ihh1 = [np.nan, np.nan, np.nan, np.nan]
        assert_array_nanclose(expect_ihh1, ihh1)

        ihh0, ihh1 = ihh01_scan_int8(h, pos, min_ehh=None)
        expect_ihh0 = [0, 10, 20, 30]
        assert_array_nanclose(expect_ihh0, ihh0)
        expect_ihh1 = [0, 10, 20, 30]
        assert_array_nanclose(expect_ihh1, ihh1)

        # case 4
        h = np.array([[0, 0, 1, 1, 1, 0],
                      [0, 1, 0, 1, 0, 1],
                      [1, 0, 0, 0, 1, 1],
                      [0, 0, 0, 1, 1, 1]], dtype='i1')

        ihh0, ihh1 = ihh01_scan_int8(h, pos, min_ehh=0.05)
        expect_ihh0 = [np.nan, np.nan, np.nan, 10*2/3]
        assert_array_nanclose(expect_ihh0, ihh0)
        expect_ihh1 = [np.nan, np.nan, np.nan, 10*2/3]
        assert_array_nanclose(expect_ihh1, ihh1)

        ihh0, ihh1 = ihh01_scan_int8(h, pos, min_ehh=None)
        expect_ihh0 = [0, 10*2/3, 10*2/3, 10*2/3]
        assert_array_nanclose(expect_ihh0, ihh0)
        expect_ihh1 = [0, 10*2/3, 10*2/3, 10*2/3]
        assert_array_nanclose(expect_ihh1, ihh1)
