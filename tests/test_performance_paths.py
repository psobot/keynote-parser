"""Tests for the shortcuts taken on the hot paths.

These are correctness tests, not benchmarks: each optimisation skips work, and
what matters is that skipping it changes nothing observable.
"""

import io
import zipfile

import pytest
import yaml

from keynote_parser import file_utils
from keynote_parser.codec import IWAFile
from keynote_parser.replacement import Replacement

TABLE_FILENAME = "./tests/data/table.key"


def _iwa_names(path):
    with zipfile.ZipFile(path) as archive:
        return [n for n in archive.namelist() if n.endswith(".iwa")]


def test_ls_does_not_decode_archives(monkeypatch):
    """`ls` prints names, so it must not pay to parse every archive."""
    calls = []
    original = IWAFile.from_buffer

    def counting_from_buffer(*args, **kwargs):
        calls.append(args[1] if len(args) > 1 else None)
        return original(*args, **kwargs)

    monkeypatch.setattr(IWAFile, "from_buffer", counting_from_buffer)

    with file_utils.file_sink("-") as sink:
        for name, handle in file_utils.file_reader(TABLE_FILENAME, False):
            file_utils.process_file(name, handle, sink)

    assert calls == [], f"ls decoded {len(calls)} archives it never looked at"


def test_ls_still_lists_every_file(capsys):
    with file_utils.file_sink("-") as sink:
        for name, handle in file_utils.file_reader(TABLE_FILENAME, False):
            file_utils.process_file(name, handle, sink)
    printed = set(capsys.readouterr().out.split())

    with zipfile.ZipFile(TABLE_FILENAME) as archive:
        expected = {n for n in archive.namelist() if not n.endswith("/")}
    assert printed == expected


def test_ls_of_a_directory_strips_the_yaml_suffix(tmp_path, capsys):
    """Unpacked directories hold .iwa.yaml; `ls` has always reported .iwa."""
    out = str(tmp_path / "unpacked")
    file_utils.process(TABLE_FILENAME, out)
    capsys.readouterr()

    with file_utils.file_sink("-") as sink:
        for name, handle in file_utils.file_reader(out, False):
            file_utils.process_file(name, handle, sink)
    printed = set(capsys.readouterr().out.split())

    assert any(n.endswith(".iwa") for n in printed)
    assert not any(n.endswith(".yaml") for n in printed)


@pytest.mark.parametrize("with_replacement", [False, True])
def test_yaml_output_is_unchanged_by_the_shortcuts(tmp_path, with_replacement):
    """The dict handed to a YAML sink must serialize exactly as an IWAFile would."""
    name = _iwa_names(TABLE_FILENAME)[0]
    with zipfile.ZipFile(TABLE_FILENAME) as archive:
        file = IWAFile.from_buffer(archive.read(name), name)

    data = file.to_dict()
    if with_replacement:
        data = Replacement("e", "E").perform_on(data)

    # What a YAML sink now writes, versus rebuilding an IWAFile first.
    direct = file_utils.dump_yaml(file_utils.to_yaml_data(data))
    roundtripped = file_utils.dump_yaml(
        file_utils.to_yaml_data(IWAFile.from_dict(data))
    )
    assert direct == roundtripped


def test_memoizing_dumper_matches_the_plain_one():
    with zipfile.ZipFile(TABLE_FILENAME) as archive:
        names = _iwa_names(TABLE_FILENAME)[:6]
        dicts = [IWAFile.from_buffer(archive.read(n), n).to_dict() for n in names]

    for data in dicts:
        expected = yaml.dump(
            data,
            default_flow_style=False,
            encoding="utf-8",
            Dumper=file_utils.Dumper,
        )
        assert file_utils.dump_yaml(data) == expected


def test_memoizing_dumper_resolves_ambiguous_scalars_correctly():
    """Values that look like other types must keep their quoting."""
    tricky = {
        "digits": "123",
        "float_ish": "1.5",
        "bool_ish": ["yes", "no", "true", "false", "on", "off"],
        "null_ish": ["null", "~", ""],
        "real_int": 123,
        "real_bool": True,
        "real_none": None,
        "sexagesimal": "1:30",
        "leading_zero": "007",
    }
    memoized = file_utils.dump_yaml(tricky)
    plain = yaml.dump(
        tricky, default_flow_style=False, encoding="utf-8", Dumper=file_utils.Dumper
    )
    assert memoized == plain
    # And it must survive a round trip unchanged.
    assert yaml.load(io.BytesIO(memoized), Loader=file_utils.Loader) == tricky
