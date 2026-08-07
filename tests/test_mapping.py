"""Tests for the generated TSP registry -> Protobuf class mappings.

The mappings are generated code (see dumper/generate_mapping.py), but a gap in
them is invisible until a real document happens to contain the missing message
type - at which point parsing fails hard. These tests assert the mapping is
complete so that gap shows up in CI instead.
"""

import pytest

from keynote_parser.versions import VERSIONS
from keynote_parser.versions.v14_4 import mapping as latest_mapping

# Nested messages (i.e. those declared inside another message) are referenced by
# the TSP registry exactly like top-level ones, but do not appear in a file
# descriptor's message_types_by_name. Forgetting to walk into them left 6383
# unmapped, which broke parsing of Index/CalculationEngine.iwa for every
# document containing a grouped table. See issues #64, #66 and #70.
NESTED_MESSAGE_TYPE_ID = 6383
NESTED_MESSAGE_TYPE_NAME = "TST.GroupByArchive.GroupNodeArchive"


def test_every_registry_id_resolves_to_a_class():
    unresolved = {
        int(type_id): name
        for type_id, name in latest_mapping.TSPRegistryMapping.items()
        if int(type_id) not in latest_mapping.ID_NAME_MAP
    }
    assert not unresolved, (
        f"{len(unresolved)} TSP registry entries have no Protobuf class; "
        "documents containing these message types will fail to parse: "
        f"{sorted(unresolved.items())[:10]}"
    )


def test_nested_message_types_are_mapped():
    assert NESTED_MESSAGE_TYPE_NAME in latest_mapping.NAME_CLASS_MAP
    assert NESTED_MESSAGE_TYPE_ID in latest_mapping.ID_NAME_MAP
    assert (
        latest_mapping.ID_NAME_MAP[NESTED_MESSAGE_TYPE_ID].DESCRIPTOR.full_name
        == NESTED_MESSAGE_TYPE_NAME
    )


def test_deeply_nested_message_types_are_mapped():
    # GroupNodeArchive itself contains a FormatManagerArchive, which in turn
    # contains a RowSetArchive - so collection has to recurse, not just descend
    # one level.
    assert (
        "TST.GroupByArchive.GroupNodeArchive.FormatManagerArchive.RowSetArchive"
        in latest_mapping.NAME_CLASS_MAP
    )


@pytest.mark.parametrize("version", VERSIONS, ids=lambda v: v.short_version_string)
def test_mapping_is_importable_for_every_supported_version(version):
    import importlib

    module = importlib.import_module(
        f"keynote_parser.versions.v{version.short_version_string.replace('.', '_')}.mapping"
    )
    assert module.ID_NAME_MAP
    assert module.NAME_CLASS_MAP
