"""Tests for the compressed descriptor archive.

The archive replaces one generated Python module per schema per version, so
these check that what comes out of it is equivalent to what those modules
provided, and that the loading machinery around it behaves.
"""

import concurrent.futures
import threading

import pytest

from keynote_parser import codec
from keynote_parser.versions import VERSIONS, archive

ALL_VERSIONS = [version.short_version_string for version in VERSIONS]


def test_every_bundled_version_is_in_the_archive():
    assert archive.bundled_versions() == sorted(ALL_VERSIONS)


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_each_version_gets_a_populated_pool(version):
    pool = archive.pool_for(version)
    assert pool.FindMessageTypeByName("TSP.Reference")
    assert pool.FindMessageTypeByName(codec.ARCHIVE_INFO_MESSAGE)


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_pools_are_cached_not_rebuilt(version):
    assert archive.pool_for(version) is archive.pool_for(version)


def test_versions_do_not_share_a_pool():
    pools = [id(archive.pool_for(v)) for v in ALL_VERSIONS]
    assert len(set(pools)) == len(ALL_VERSIONS)


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_registry_entries_resolve_to_classes(version):
    id_name_map, name_class_map = archive.compute_maps(version)
    registry = archive.registry_for(version)
    # Some very old versions genuinely lack protos for a few registry entries.
    assert len(id_name_map) >= len(registry) - 3
    for message_class in id_name_map.values():
        assert message_class.DESCRIPTOR.full_name in name_class_map


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_nested_messages_are_reachable(version):
    _, name_class_map = archive.compute_maps(version)
    nested = [name for name in name_class_map if name.count(".") > 1]
    assert nested, "no nested message types found; the walk is not recursing"


def test_classes_are_usable_protobuf_messages():
    reference = archive.message_class(ALL_VERSIONS[-1], "TSP.Reference")
    instance = reference()
    instance.identifier = 42
    assert reference.FromString(instance.SerializeToString()).identifier == 42


def test_unknown_version_raises_a_clear_error():
    with pytest.raises(KeyError, match="99.9"):
        archive.pool_for("99.9")
    with pytest.raises(KeyError, match="99.9"):
        archive.registry_for("99.9")


def test_the_module_lock_is_reentrant():
    """pool_for() holds the lock while calling _read_archive(), which takes it too.

    Asserted directly rather than by exercising the path, because a plain Lock
    doesn't fail there - it hangs, and a hanging test is worse than a failing
    one. The two tests below do exercise it, under timeouts.
    """
    assert isinstance(archive._lock, type(threading.RLock()))


def test_first_use_from_a_single_thread_completes():
    archive._pools.clear()
    archive._registries.clear()
    archive._archive = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        id_name_map, _ = pool.submit(archive.compute_maps, ALL_VERSIONS[0]).result(
            timeout=60
        )
    assert id_name_map


def test_concurrent_first_use_does_not_deadlock():
    archive._pools.clear()
    archive._registries.clear()
    archive._archive = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(archive.compute_maps, version) for version in ALL_VERSIONS
        ]
        results = [f.result(timeout=120) for f in futures]

    assert all(id_name_map for id_name_map, _ in results)
