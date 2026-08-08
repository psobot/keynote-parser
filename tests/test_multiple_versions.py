"""Tests that several bundled Keynote versions can coexist in one process.

Generated Protobuf code registers into `descriptor_pool.Default()`, which is
global and keyed by .proto filename. Every Keynote version compiles the same
filenames, so before each version got its own pool, importing a second one
raised:

    TypeError: Couldn't build proto file into descriptor pool:
               duplicate file name TSDArchives.proto

which made the versions/ layout unusable for the thing it exists to do.
"""

import itertools

import pytest

from keynote_parser import codec
from keynote_parser.versions import LATEST_VERSION, VERSIONS

SIMPLE_FILENAME = "./tests/data/simple-oneslide.iwa"

# Keynote 14.5 ships the same schemas as 14.4, so it is bundled primarily to
# keep the multi-version machinery exercised rather than decorative.
ALL_VERSIONS = [version.short_version_string for version in VERSIONS]


def test_more_than_one_version_is_bundled():
    assert len(ALL_VERSIONS) >= 2, (
        "these tests only mean anything with two or more versions bundled; "
        f"found {ALL_VERSIONS}"
    )


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_every_bundled_version_imports(version):
    id_name_map, name_class_map, archive_info = codec.import_version(version)
    assert id_name_map and name_class_map and archive_info


def test_versions_do_not_share_a_descriptor_pool():
    pools = {}
    for version in ALL_VERSIONS:
        klass = codec.import_version(version)[0][6383]
        pools[version] = klass.DESCRIPTOR.file.pool

    distinct = {id(pool) for pool in pools.values()}
    assert len(distinct) == len(ALL_VERSIONS), (
        f"expected one pool per version, got {len(distinct)} for {ALL_VERSIONS}"
    )


def test_versions_yield_distinct_message_classes():
    for a, b in itertools.combinations(ALL_VERSIONS, 2):
        klass_a = codec.import_version(a)[0][6383]
        klass_b = codec.import_version(b)[0][6383]
        # Same protobuf type name, different generated class per version.
        assert klass_a.DESCRIPTOR.full_name == klass_b.DESCRIPTOR.full_name
        assert klass_a is not klass_b


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_extension_fields_resolve_within_each_version(version):
    # The #54 chart fix looks extensions up in a descriptor pool. With private
    # pools it must consult the pool the class was built in, not the default
    # one - which now contains none of these.
    name_class_map = codec.import_version(version)[1]
    klass = name_class_map["TSCH.ChartDrawableArchive"]
    extension = klass.DESCRIPTOR.file.pool.FindExtensionByNumber(
        klass.DESCRIPTOR, 10000
    )
    assert extension.message_type.full_name == "TSCH.ChartArchive"


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_a_document_parses_under_each_version(version):
    with open(SIMPLE_FILENAME, "rb") as f:
        data = f.read()
    file = codec.IWAArchiveSegment.from_buffer(
        b"".join(codec.IWACompressedChunk._decompress_all(data)), version=version
    )
    assert file[0].objects


def test_latest_version_is_the_highest_and_is_stable():
    assert LATEST_VERSION == max(VERSIONS)
    # VERSIONS comes from os.listdir(), so re-sorting must not change the answer.
    for ordering in itertools.permutations(VERSIONS):
        assert max(ordering) == LATEST_VERSION


def test_default_version_is_the_latest():
    assert codec.LATEST_VERSION == LATEST_VERSION.short_version_string
