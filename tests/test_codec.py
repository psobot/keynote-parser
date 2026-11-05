try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader

import pytest
import yaml
from google.protobuf.json_format import MessageToDict, ParseDict

from keynote_parser import codec
from keynote_parser.unicode_utils import fix_unicode
from keynote_parser.versions.archive import message_class

Archive = message_class("14.4", "TSCH.Generated.ChartSeriesStyleArchive")

SIMPLE_FILENAME = "./tests/data/simple-oneslide.iwa"
MULTILINE_FILENAME = "./tests/data/multiline-oneslide.iwa"
MULTICHUNK_FILENAME = "./tests/data/multi-chunk.iwa"
EMOJI_FILENAME = "./tests/data/emoji-oneslide.iwa"
MESSAGE_TYPE_ZERO_FILENAME = "./tests/data/message-type-zero.iwa"
EMOJI_FILENAME_PY2_YAML = "./tests/data/emoji-oneslide.py2.yaml"
EMOJI_FILENAME_PY3_YAML = "./tests/data/emoji-oneslide.py3.yaml"
VERY_BIG_SLIDE = "./tests/data/very-big-slide.iwa"
MAX_FLOAT = 340282346638528859811704183484516925440.0000000000000000000000
TOO_BIG_FLOAT = 3.4028235e38


def roundtrip(filename):
    with open(filename, "rb") as f:
        test_data = f.read()
    file = codec.IWAFile.from_buffer(test_data, filename)
    roundtrip_iwa_file(file, test_data)


def roundtrip_iwa_file(file, binary):
    assert file is not None
    for chunk in file.chunks:
        for archive in chunk.archives:
            assert (
                codec.IWAArchiveSegment.from_buffer(archive.to_buffer())[0] == archive
            )
        assert codec.IWACompressedChunk.from_buffer(chunk.to_buffer())[0] == chunk
    assert codec.IWAFile.from_buffer(file.to_buffer()).to_dict() == file.to_dict()


def test_iwa_simple_roundtrip():
    roundtrip(SIMPLE_FILENAME)


def test_iwa_multiline_roundtrip():
    roundtrip(MULTILINE_FILENAME)


def test_iwa_emoji_roundtrip():
    roundtrip(EMOJI_FILENAME)


def test_iwa_message_type_zero_roundtrip():
    roundtrip(MESSAGE_TYPE_ZERO_FILENAME)


def test_yaml_parse_py2_emoji():
    with open(EMOJI_FILENAME_PY2_YAML, "rb") as handle:
        file = codec.IWAFile.from_dict(
            yaml.safe_load(fix_unicode(handle.read().decode("utf-8")))
        )
        assert file is not None


def test_yaml_parse_py3_emoji():
    with open(EMOJI_FILENAME_PY3_YAML, "rb") as handle:
        file = codec.IWAFile.from_dict(
            yaml.safe_load(fix_unicode(handle.read().decode("utf-8")))
        )
        assert file is not None


def test_iwa_multichunk_roundtrip():
    with open(MULTICHUNK_FILENAME, "rb") as f:
        test_data = f.read()
    file = codec.IWAFile.from_buffer(test_data, MULTICHUNK_FILENAME)
    assert file is not None
    rt_as_dict = codec.IWAFile.from_buffer(
        file.to_buffer(), MULTICHUNK_FILENAME
    ).to_dict()
    assert rt_as_dict == file.to_dict()


def test_roundtrip_very_big():
    roundtrip(VERY_BIG_SLIDE)


@pytest.mark.parametrize("big_float", (MAX_FLOAT, TOO_BIG_FLOAT))
def test_too_big_float_deserialization(big_float):
    test_archive = Archive(tschchartseriesareasymbolsize=big_float)
    test_archive_as_dict = MessageToDict(test_archive)
    serialized = yaml.dump(test_archive_as_dict, Dumper=Dumper)
    deserialized = yaml.load(serialized, Loader=Loader)
    deserialized = codec._work_around_protobuf_max_float_handling(deserialized)
    deserialized_as_message = ParseDict(deserialized, Archive())
    assert deserialized_as_message == test_archive


def _archive_payloads(iwa_file):
    return [
        [obj.SerializeToString() for obj in archive.objects]
        for chunk in iwa_file.chunks
        for archive in chunk.archives
    ]


def test_yaml_roundtrip_is_byte_identical():
    # The YAML form sorts keys, so extensions come back in alphabetical order
    # of their names. They must still be serialized in field-number order, as
    # Keynote wrote them: KN.ThemeArchive's presets (extensions 100 to 210 of
    # TSS.ThemeArchive) otherwise come out reordered in every Document.iwa.
    import zipfile

    from keynote_parser.file_utils import dump_yaml

    with zipfile.ZipFile("./tests/data/simple-oneslide.key") as zf:
        original = codec.IWAFile.from_buffer(zf.read("Index/Document.iwa"))
    data = yaml.load(
        fix_unicode(dump_yaml(original.to_dict()).decode("utf-8")), Loader=Loader
    )
    assert _archive_payloads(codec.IWAFile.from_dict(data)) == _archive_payloads(
        original
    )
