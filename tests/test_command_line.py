"""Tests for the command-line interface.

The CLI is how nearly everyone uses this package, and it had no coverage at
all: argument wiring, defaults and dispatch were entirely untested.
"""

import json
import zipfile

import pytest

from keynote_parser import __version__, command_line

TABLE_FILENAME = "./tests/data/table.key"


@pytest.fixture
def run(monkeypatch):
    """Invoke main() as the console script would, with the given argv."""

    def _run(*argv):
        monkeypatch.setattr("sys.argv", ["keynote-parser", *argv])
        return command_line.main()

    return _run


@pytest.fixture
def replacements_file(tmp_path):
    def _write(replacements):
        path = tmp_path / "replacements.json"
        path.write_text(json.dumps({"replacements": replacements}))
        return str(path)

    return _write


@pytest.mark.parametrize(
    "argv, expected_func",
    [
        (["unpack", "x.key"], "unpack_command"),
        (["pack", "somedir"], "pack_command"),
        (["ls", "x.key"], "ls_command"),
        (["cat", "x.key", "Index/Document.iwa"], "cat_command"),
        (["replace", "x.key"], "replace_command"),
    ],
)
def test_subcommands_dispatch(monkeypatch, run, argv, expected_func):
    called = {}
    monkeypatch.setattr(
        command_line,
        expected_func,
        lambda *a, **kw: called.setdefault("hit", (a, kw)),
    )
    run(*argv)
    assert "hit" in called, f"{argv[0]} did not dispatch to {expected_func}"


@pytest.mark.parametrize(
    "argv, key, expected",
    [
        (["unpack", "x.key"], "output", None),
        (["unpack", "x.key", "--output", "out"], "output", "out"),
        (["unpack", "x.key", "-o", "out"], "output", "out"),
        (["cat", "x.key", "F.iwa"], "raw", False),
        (["cat", "x.key", "F.iwa", "--raw"], "raw", True),
        (["replace", "x.key", "--find", "a", "--replace", "b"], "find", "a"),
        (["replace", "x.key", "--find", "a", "--replace", "b"], "replace", "b"),
    ],
)
def test_arguments_reach_the_command(monkeypatch, run, argv, key, expected):
    seen = {}
    for name in ("unpack_command", "cat_command", "replace_command"):
        monkeypatch.setattr(command_line, name, lambda **kw: seen.update(kw))
    run(*argv)
    assert seen.get(key) == expected


def test_version_flag_prints_the_version(run, capsys):
    with pytest.raises(SystemExit) as excinfo:
        run("--version")
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == __version__


def test_no_arguments_prints_help(run, capsys):
    run()
    assert "manipulate Apple Keynote .key files" in capsys.readouterr().out


@pytest.mark.parametrize(
    "kwargs, expected_count",
    [
        ({}, 0),
        ({"replacements": None}, 0),
    ],
)
def test_parse_replacements_without_a_file(kwargs, expected_count):
    assert len(command_line.parse_replacements(**kwargs)) == expected_count


def test_parse_replacements_reads_the_file(replacements_file):
    path = replacements_file([{"find": "a", "replace": "b"}])
    parsed = command_line.parse_replacements(replacements=path)
    assert [(r.find, r.replace) for r in parsed] == [("a", "b")]


def test_replace_without_any_replacements_warns_and_does_nothing(capsys):
    command_line.replace_command(TABLE_FILENAME, output=None)
    assert "No replacements passed" in capsys.readouterr().out


@pytest.mark.parametrize(
    "count, expected",
    [(1, "Replaced 'a' with 'b'."), (3, "Replaced 'a' with 'b' 3 times.")],
)
def test_replace_reports_singular_and_plural(monkeypatch, capsys, count, expected):
    monkeypatch.setattr(command_line, "process", lambda *a, **kw: [("a", "b")] * count)
    command_line.replace_command(TABLE_FILENAME, find="a", replace="b")
    assert expected in capsys.readouterr().out


def test_unpack_defaults_output_to_the_input_without_extension(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        command_line, "process", lambda i, o, **kw: seen.update(input=i, output=o)
    )
    command_line.unpack_command("MyDeck.key")
    assert seen["output"] == "MyDeck"


def test_pack_defaults_output_to_the_input_plus_extension(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        command_line, "process", lambda i, o, **kw: seen.update(input=i, output=o)
    )
    command_line.pack_command("MyDeck")
    assert seen["output"] == "MyDeck.key"


def test_cat_decodes_to_yaml(capsys):
    command_line.cat_command(TABLE_FILENAME, "Index/Document.iwa", raw=False)
    assert "_pbtype" in capsys.readouterr().out


def test_cat_raw_emits_the_original_bytes(capsysbinary):
    # --raw writes the undecoded .iwa straight to stdout, so this has to be
    # captured as bytes; it is not valid UTF-8.
    command_line.cat_command(TABLE_FILENAME, "Index/Document.iwa", raw=True)
    written = capsysbinary.readouterr().out

    with zipfile.ZipFile(TABLE_FILENAME) as archive:
        assert written == archive.read("Index/Document.iwa")


def test_ls_lists_every_entry(capsys):
    command_line.ls_command(TABLE_FILENAME)
    printed = set(capsys.readouterr().out.split())
    with zipfile.ZipFile(TABLE_FILENAME) as archive:
        assert printed == {n for n in archive.namelist() if not n.endswith("/")}


def test_unpack_then_pack_round_trips(tmp_path, capsys):
    unpacked = str(tmp_path / "unpacked")
    repacked = str(tmp_path / "repacked.key")
    command_line.unpack_command(TABLE_FILENAME, output=unpacked)
    command_line.pack_command(unpacked, output=repacked)

    with (
        zipfile.ZipFile(TABLE_FILENAME) as original,
        zipfile.ZipFile(repacked) as result,
    ):
        assert set(original.namelist()) == set(result.namelist())
