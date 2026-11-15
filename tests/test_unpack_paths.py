# -*- coding: utf-8 -*-
"""Unpacking a document must never write outside of the output directory.

The archive members' names come from the document, which may be untrusted.
"""

import os
import zipfile

import pytest

from keynote_parser import file_utils

SIMPLE_FILENAME = "./tests/data/simple-oneslide.key"


def _all_files(root):
    return sorted(
        os.path.relpath(os.path.join(dirpath, name), root)
        for dirpath, _, names in os.walk(root)
        for name in names
    )


def _all_dirs(root):
    return sorted(
        os.path.relpath(os.path.join(dirpath, name), root)
        for dirpath, names, _ in os.walk(root)
        for name in names
    )


def _write_key(path, names):
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, b"attacker-controlled")


@pytest.fixture
def sandbox(tmp_path):
    """An output directory nested deep inside tmp_path.

    Any ".." hop or absolute path used by the tests stays inside tmp_path, so the
    tests are harmless even if the code under test does not confine writes.
    """
    output = tmp_path / "a" / "b" / "out"
    output.mkdir(parents=True)
    return tmp_path, output


@pytest.mark.parametrize(
    "name",
    [
        "../escaped.bin",
        "../../escaped.bin",
        "../../../escaped.bin",
        "Data/../../escaped.bin",
        "Data/../../../escaped.bin",
        "Index/sub/../../../../escaped.bin",
        "newdir/../../../escaped.bin",
    ],
)
def test_traversal_member_is_rejected(sandbox, name):
    root, output = sandbox
    key = root / "evil.key"
    _write_key(key, [name])
    before_files, before_dirs = _all_files(root), _all_dirs(root)

    with pytest.raises(ValueError, match="outside of the output directory"):
        file_utils.process(str(key), str(output))

    # Nothing was created, outside of the output directory or inside it.
    assert _all_files(root) == before_files
    assert _all_dirs(root) == before_dirs


def test_absolute_member_is_rejected(sandbox):
    root, output = sandbox
    victim = root / "absolute-target.bin"
    key = root / "evil.key"
    _write_key(key, [str(victim)])

    with pytest.raises(ValueError, match="outside of the output directory"):
        file_utils.process(str(key), str(output))

    assert not victim.exists()


def test_directories_are_not_created_outside_of_the_output_directory(sandbox):
    root, output = sandbox
    key = root / "evil.key"
    _write_key(key, ["../../new/nested/dir/escaped.bin"])

    with pytest.raises(ValueError):
        file_utils.process(str(key), str(output))

    assert not (root / "a" / "new").exists()


@pytest.mark.parametrize("raw", [True, False])
def test_traversal_is_rejected_for_iwa_contents(sandbox, raw):
    root, output = sandbox
    with file_utils.dir_file_sink(str(output), raw=raw) as sink:
        with pytest.raises(ValueError, match="outside of the output directory"):
            # A dict is written as YAML (".yaml" is appended) unless `raw`.
            sink("../../escaped.iwa", {"archives": []})

    assert not (root / "a" / "escaped.iwa").exists()
    assert not (root / "a" / "escaped.iwa.yaml").exists()


def test_iwa_contents_are_still_written_as_yaml_inside(sandbox):
    root, output = sandbox
    with file_utils.dir_file_sink(str(output)) as sink:
        sink("Index/Document.iwa", {"archives": []})

    assert _all_files(output) == [os.path.join("Index", "Document.iwa.yaml")]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlink support")
def test_member_through_a_symlink_to_outside_is_rejected(sandbox):
    root, output = sandbox
    outside = root / "outside"
    outside.mkdir()
    try:
        os.symlink(outside, output / "link")
    except OSError:
        pytest.skip("cannot create symlinks")
    key = root / "evil.key"
    _write_key(key, ["link/escaped.bin"])

    with pytest.raises(ValueError, match="outside of the output directory"):
        file_utils.process(str(key), str(output))

    assert _all_files(outside) == []


def test_member_with_dots_inside_a_name_is_still_written(sandbox):
    root, output = sandbox
    key = root / "fine.key"
    names = ["Data/a..b.bin", "Data/..hidden.bin", "Index/sub/dir/ok.bin", "Index/x/./y.bin"]
    _write_key(key, names)

    file_utils.process(str(key), str(output))

    assert _all_files(output) == sorted(
        [
            os.path.join("Data", "a..b.bin"),
            os.path.join("Data", "..hidden.bin"),
            os.path.join("Index", "sub", "dir", "ok.bin"),
            os.path.join("Index", "x", "y.bin"),
        ]
    )


def test_unpacking_a_real_document_still_works(tmp_path):
    output = tmp_path / "out"

    file_utils.process(SIMPLE_FILENAME, str(output))

    files = _all_files(output)
    assert os.path.join("Index", "Document.iwa.yaml") in files
    assert any(f.startswith("Data" + os.sep) for f in files)


def test_is_within_directory(tmp_path):
    directory = tmp_path / "dir"
    directory.mkdir()
    assert file_utils.is_within_directory(directory, directory / "file")
    assert file_utils.is_within_directory(directory, directory / "a" / ".." / "file")
    assert not file_utils.is_within_directory(directory, directory)
    assert not file_utils.is_within_directory(directory, tmp_path / "file")
    assert not file_utils.is_within_directory(directory, directory / ".." / "file")
    # A sibling sharing the directory's name as a prefix is not inside it.
    assert not file_utils.is_within_directory(directory, tmp_path / "dir2" / "file")
