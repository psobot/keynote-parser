"""Tests for replacing images inside a .key file.

This path had no coverage at all, which is how `Image.ANTIALIAS` survived in
file_utils for two years after Pillow 10 removed it (see #59): every user's
image replacement raised AttributeError and nothing in CI noticed. These tests
drive the real code path against a real .key file so that a regression in it
fails here rather than in the field.
"""

import hashlib
import zipfile

from PIL import Image

from keynote_parser import file_utils
from keynote_parser.replacement import Replacement

TABLE_FILENAME = "./tests/data/table.key"

# Both Data/ assets in table.key are size variants of one image, named
# <stem>-<size>.jpg. Replacement matches on the stem, so both should be hit.
ASSET_STEM = "st-8B4A13BB-29F7-48A4-9D9C-F0C7B6E9264B"


def _assets(path):
    with zipfile.ZipFile(path) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith("Data/")
        }


def _digests(path):
    with zipfile.ZipFile(path) as archive:
        return {
            name: hashlib.md5(archive.read(name)).hexdigest()
            for name in archive.namelist()
        }


def _write_image(path, size=(1200, 900), color=(200, 30, 30)):
    Image.new("RGB", size, color).save(path)
    return str(path)


def _replace(tmp_path, find, image_size=(1200, 900)):
    replacement_image = _write_image(tmp_path / "replacement.jpg", size=image_size)
    output = str(tmp_path / "out.key")
    file_utils.process(
        TABLE_FILENAME, output, replacements=[Replacement(find, replacement_image)]
    )
    return output


def test_matching_assets_are_rewritten(tmp_path):
    before = _assets(TABLE_FILENAME)
    assert before, "fixture should contain Data/ assets"

    output = _replace(tmp_path, f"{ASSET_STEM}.jpg")
    after = _assets(output)

    assert set(after) == set(before)
    for name in before:
        assert after[name] != before[name], f"{name} was not replaced"


def test_replacement_is_scaled_to_each_original(tmp_path):
    # The replacement is deliberately larger than either variant; each asset
    # should come back no larger than the one it replaced, so that a single
    # source image can stand in for every size Keynote generated.
    before = _assets(TABLE_FILENAME)
    original_sizes = {
        name: Image.open(zipfile.ZipFile(TABLE_FILENAME).open(name)).size
        for name in before
    }

    output = _replace(tmp_path, f"{ASSET_STEM}.jpg", image_size=(1200, 900))

    with zipfile.ZipFile(output) as archive:
        for name, original_size in original_sizes.items():
            new_size = Image.open(archive.open(name)).size
            assert new_size[0] <= original_size[0]
            assert new_size[1] <= original_size[1]


def test_replacement_preserves_the_original_format(tmp_path):
    output = _replace(tmp_path, f"{ASSET_STEM}.jpg")
    with zipfile.ZipFile(output) as archive:
        for name in _assets(output):
            assert Image.open(archive.open(name)).format == "JPEG"


def test_non_matching_replacement_changes_nothing(tmp_path):
    before = _digests(TABLE_FILENAME)
    output = _replace(tmp_path, "no-such-image.jpg")
    after = _digests(output)

    assert set(after) == set(before)
    unchanged = [name for name in before if before[name] == after[name]]
    # .iwa files are re-serialized on the way through, so only assert that the
    # Data/ assets - the things a replacement would have touched - are intact.
    assert all(name in unchanged for name in before if name.startswith("Data/"))


def test_output_is_still_a_readable_keynote_archive(tmp_path):
    output = _replace(tmp_path, f"{ASSET_STEM}.jpg")

    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        names = archive.namelist()

    assert "Index/Document.iwa" in names
    # And the result must still parse as Keynote data, not just as a zip.
    for name, handle in file_utils.file_reader(output, False):
        if name == "Index/Document.iwa":
            assert codec_parses(handle.read(), name)
            break
    else:
        raise AssertionError("Index/Document.iwa missing from output")


def codec_parses(data, name):
    from keynote_parser.codec import IWAFile

    return IWAFile.from_buffer(data, name) is not None
