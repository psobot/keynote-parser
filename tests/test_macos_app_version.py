"""Tests for MacOSAppVersion ordering.

Version ordering is load-bearing in two places: LATEST_VERSION is `max(VERSIONS)`,
and the "your Keynote is newer than this parser supports" warning compares the
installed version against the supported one. Both were unreliable, which only
stayed invisible because exactly one version has ever been bundled.
"""

import itertools

import pytest

from keynote_parser.macos_app_version import MacOSAppVersion as V

# The two versions this actually matters for.
V14_4 = V("14.4", "7043.0.93", "1A89s")
V14_5 = V("14.5", "7045.0.17", "1A107s")


def test_ordering_is_antisymmetric():
    # Previously both directions were True: the old __lt__ OR'd three
    # independent comparisons, and "1A107s" < "1A89s" as a plain string.
    assert V14_4 < V14_5
    assert not V14_5 < V14_4


def test_latest_version_does_not_depend_on_iteration_order():
    # VERSIONS is built from os.listdir(), so max() must not care about order.
    for ordering in itertools.permutations([V14_4, V14_5]):
        assert max(ordering) == V14_5
        assert min(ordering) == V14_4


def test_build_version_digits_compare_numerically():
    # "1A89s" vs "1A107s": as strings "1A107s" sorts first, which is wrong.
    older = V("14.4", "7043.0.93", "1A89s")
    newer = V("14.4", "7043.0.93", "1A107s")
    assert older < newer
    assert not newer < older


def test_bundle_version_digits_compare_numerically():
    older = V("14.4", "7043.0.9", "1A89s")
    newer = V("14.4", "7043.0.93", "1A89s")
    assert older < newer


def test_short_versions_of_differing_length_compare_correctly():
    # The old comparator scaled by 10 ** (len - i), so "14.4.1" scored 14410
    # and "14.5" scored 1450 - making the older release sort higher.
    assert V("14.4.1", "a", "a") < V("14.5", "a", "a")
    assert V("14.4", "a", "a") < V("14.4.1", "a", "a")
    assert V("9.2", "a", "a") < V("14.4", "a", "a")


def test_equality_and_hashing():
    assert V14_4 == V("14.4", "7043.0.93", "1A89s")
    assert V14_4 != V14_5
    assert len({V14_4, V("14.4", "7043.0.93", "1A89s")}) == 1
    assert len({V14_4, V14_5}) == 2


def test_comparison_against_other_types_is_rejected():
    with pytest.raises(TypeError):
        V14_4 < "14.4"
    assert V14_4 != "14.4"


def test_ordering_is_transitive_across_a_realistic_range():
    versions = [
        V("9.2", "6520", "1A100s"),
        V("12.2.1", "7035.0.161", "1A200s"),
        V("13.1", "7038.0.85", "1A300s"),
        V14_4,
        V14_5,
        V("15.1.1", "7050.0.11", "1B10s"),
    ]
    assert sorted(versions, reverse=True)[0] == V("15.1.1", "7050.0.11", "1B10s")
    for earlier, later in zip(versions, versions[1:]):
        assert earlier < later, f"{earlier} should sort before {later}"


def test_major_and_minor():
    assert V14_5.major == 14
    assert V14_5.minor == 5
    assert V("15.1.1", "a", "a").major == 15
