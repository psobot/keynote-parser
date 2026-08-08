"""Tests for choosing which Keynote version's schemas to read and write with.

Message names changed between Keynote releases - KN.CommandChangeMasterSlideArchive
became KN.CommandChangeTemplateSlideArchive, and 20-odd others like it - so a
.yaml file written by an older keynote-parser names types that the newest
schemas no longer contain. Selecting a version is what makes those files
readable, which is the caveat the README's Compatibility section describes.
"""

import zipfile

import pytest

from keynote_parser import codec, file_utils
from keynote_parser.versions import LATEST_VERSION, VERSIONS

ALL_VERSIONS = [version.short_version_string for version in VERSIONS]
TABLE_FILENAME = "./tests/data/table.key"

# Renames happen at two boundaries only: 10.2 -> 11.2 (24 types, the
# Master -> Template rename the README describes) and 13.1 -> 14.4 (36 types).
RENAMED_TYPE_ID = 119
OLD_NAME = "KN.CommandChangeMasterSlideArchive"  # Keynote 10.2
NEW_NAME = "KN.CommandChangeTemplateSlideArchive"  # Keynote 11.2 onward
OLD_VERSION = "10.2"
NEW_VERSION = "11.2"


def _renamed_between(older, newer):
    old_map = codec.import_version(older)[0]
    new_map = codec.import_version(newer)[0]
    return {
        type_id
        for type_id in set(old_map) & set(new_map)
        if old_map[type_id].DESCRIPTOR.full_name
        != new_map[type_id].DESCRIPTOR.full_name
    }


@pytest.mark.parametrize("older, newer", [("10.2", "11.2"), ("13.1", "14.4")])
def test_message_names_really_did_change_between_versions(older, newer):
    # If these ever come back empty the feature below is pointless, so assert it.
    assert _renamed_between(older, newer)


@pytest.mark.parametrize(
    "version, expected_name",
    [("10.2", OLD_NAME), ("11.2", NEW_NAME), ("13.1", NEW_NAME), ("14.5", NEW_NAME)],
)
def test_the_same_type_id_resolves_to_each_version_s_name(version, expected_name):
    resolved = codec.import_version(version)[0][RENAMED_TYPE_ID]
    assert resolved.DESCRIPTOR.full_name == expected_name


def test_old_names_are_only_known_to_old_versions():
    assert OLD_NAME in codec.import_version(OLD_VERSION)[1]
    assert OLD_NAME not in codec.import_version(NEW_VERSION)[1]


def test_new_names_are_only_known_to_new_versions():
    assert NEW_NAME in codec.import_version(NEW_VERSION)[1]
    assert NEW_NAME not in codec.import_version(OLD_VERSION)[1]


@pytest.mark.parametrize(
    "name, version, readable",
    [
        (OLD_NAME, OLD_VERSION, True),
        (OLD_NAME, NEW_VERSION, False),
        (NEW_NAME, NEW_VERSION, True),
        (NEW_NAME, OLD_VERSION, False),
    ],
)
def test_dict_to_message_honours_the_selected_version(name, version, readable):
    """This is the mechanism that makes old .yaml loadable."""
    if readable:
        assert codec.dict_to_message({"_pbtype": name}, version=version) is not None
    else:
        with pytest.raises(KeyError):
            codec.dict_to_message({"_pbtype": name}, version=version)


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_a_document_unpacks_under_every_bundled_version(tmp_path, version):
    out = str(tmp_path / version.replace(".", "_"))
    file_utils.process(TABLE_FILENAME, out, version=version)
    assert list(tmp_path.rglob("*.yaml"))


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_unpack_then_pack_round_trips_within_a_version(tmp_path, version):
    unpacked = str(tmp_path / "unpacked")
    repacked = str(tmp_path / "repacked.key")
    file_utils.process(TABLE_FILENAME, unpacked, version=version)
    file_utils.process(unpacked, repacked, version=version)

    with (
        zipfile.ZipFile(TABLE_FILENAME) as original,
        zipfile.ZipFile(repacked) as result,
    ):
        assert set(original.namelist()) == set(result.namelist())


def test_version_defaults_to_the_newest_bundled():
    assert codec.LATEST_VERSION == LATEST_VERSION.short_version_string
    assert max(ALL_VERSIONS, key=lambda v: [int(x) for x in v.split(".")]) == (
        LATEST_VERSION.short_version_string
    )
