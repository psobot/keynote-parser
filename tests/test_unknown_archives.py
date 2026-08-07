"""Tests for graceful handling of archives we can't decode.

Apple adds Protobuf message types between Keynote releases, so a document
written by a newer Keynote than the one we have protos for will contain
archives we don't recognise. Those must not abort the whole read - see #60,
#64 and #70, where a single unknown type in Index/CalculationEngine.iwa made
`ls`, `cat` and `unpack` unusable on the entire document.
"""

import copy
import warnings

import pytest

from keynote_parser import codec

SIMPLE_FILENAME = "./tests/data/simple-oneslide.iwa"


@pytest.fixture(autouse=True)
def _reset_warning_dedupe():
    # codec only warns once per (file, type); clear that between tests.
    codec._WARNED_ABOUT.clear()


def _first_archive_type(filename):
    with open(filename, "rb") as f:
        file = codec.IWAFile.from_buffer(f.read(), filename)
    return file.chunks[0].archives[0].header.message_infos[0].type


def _first_archive_payload(filename):
    """The exact on-disk bytes of the first archive in `filename`."""
    with open(filename, "rb") as f:
        decompressed = b"".join(codec.IWACompressedChunk._decompress_all(f.read()))
    archive_info, payload = codec.get_archive_info_and_remainder(decompressed)
    return payload[: archive_info.message_infos[0].length]


def _patch_mapping(monkeypatch, id_name_map):
    _, name_class_map, archive_info = codec.import_version()
    monkeypatch.setattr(
        codec,
        "import_version",
        lambda *a, **k: (id_name_map, name_class_map, archive_info),
    )


def _read_with_type_unmapped(filename, type_id, monkeypatch):
    """Read `filename` as though `type_id` were absent from the mapping."""
    id_name_map = codec.import_version()[0]
    _patch_mapping(monkeypatch, {k: v for k, v in id_name_map.items() if k != type_id})
    with open(filename, "rb") as f:
        data = f.read()
    return codec.IWAFile.from_buffer(data, filename), data


def test_unknown_message_type_warns_instead_of_raising(monkeypatch):
    type_id = _first_archive_type(SIMPLE_FILENAME)
    with pytest.warns(codec.UnknownArchiveWarning, match=str(type_id)):
        file, _ = _read_with_type_unmapped(SIMPLE_FILENAME, type_id, monkeypatch)
    assert file is not None


def test_unknown_message_type_is_preserved_verbatim(monkeypatch):
    type_id = _first_archive_type(SIMPLE_FILENAME)
    expected = _first_archive_payload(SIMPLE_FILENAME)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", codec.UnknownArchiveWarning)
        file, _ = _read_with_type_unmapped(SIMPLE_FILENAME, type_id, monkeypatch)

        unknown = file.chunks[0].archives[0].objects[0]
        assert isinstance(unknown, codec.UnknownArchive)
        assert unknown.type_id == type_id

        # The undecoded archive must be written back byte-for-byte.
        assert unknown.data == expected
        assert unknown.SerializeToString() == expected

        # ...and the file as a whole must still round-trip.
        assert codec.IWAFile.from_buffer(file.to_buffer()).to_dict() == file.to_dict()


def test_unknown_archive_survives_a_yaml_roundtrip(monkeypatch):
    type_id = _first_archive_type(SIMPLE_FILENAME)
    expected = _first_archive_payload(SIMPLE_FILENAME)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", codec.UnknownArchiveWarning)
        file, _ = _read_with_type_unmapped(SIMPLE_FILENAME, type_id, monkeypatch)

        as_dict = file.to_dict()
        assert as_dict["chunks"][0]["archives"][0]["objects"][0]["_pbtype"] == (
            codec.UnknownArchive.PBTYPE
        )

        # Unpack -> YAML -> pack must not lose the bytes we couldn't decode.
        # (from_dict consumes the dict it's handed, so hand it a copy.)
        reparsed = codec.IWAFile.from_dict(copy.deepcopy(as_dict))
        assert reparsed.chunks[0].archives[0].objects[0].data == expected
        assert reparsed.to_dict() == as_dict


def test_undecodable_payload_is_preserved_verbatim(monkeypatch):
    """A mapped type whose payload won't parse should degrade the same way."""

    class Undecodable:
        @staticmethod
        def FromString(data):
            raise ValueError("nope")

    type_id = _first_archive_type(SIMPLE_FILENAME)
    expected = _first_archive_payload(SIMPLE_FILENAME)
    broken = dict(codec.import_version()[0])
    broken[type_id] = Undecodable
    _patch_mapping(monkeypatch, broken)

    with open(SIMPLE_FILENAME, "rb") as f:
        original = f.read()

    with pytest.warns(codec.UnknownArchiveWarning, match="Failed to deserialize"):
        file = codec.IWAFile.from_buffer(original, SIMPLE_FILENAME)

    unknown = file.chunks[0].archives[0].objects[0]
    assert isinstance(unknown, codec.UnknownArchive)
    assert unknown.data == expected


def test_unknown_archives_can_be_made_fatal(monkeypatch):
    """Callers who'd rather fail loudly can promote the warning to an error."""
    type_id = _first_archive_type(SIMPLE_FILENAME)
    with warnings.catch_warnings():
        warnings.simplefilter("error", codec.UnknownArchiveWarning)
        with pytest.raises(ValueError):
            _read_with_type_unmapped(SIMPLE_FILENAME, type_id, monkeypatch)


def test_only_warns_once_per_file_and_type(monkeypatch):
    type_id = _first_archive_type(SIMPLE_FILENAME)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", codec.UnknownArchiveWarning)
        _read_with_type_unmapped(SIMPLE_FILENAME, type_id, monkeypatch)
    relevant = [w for w in caught if w.category is codec.UnknownArchiveWarning]
    assert len(relevant) == 1
