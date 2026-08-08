"""Tests for parsing the --replacements file.

This is the documented way to drive bulk replacements, and the format is easy
to get subtly wrong, but parse_json had no coverage.
"""

import json

import pytest

from keynote_parser.replacement import Replacement, parse_json


@pytest.fixture
def written(tmp_path):
    def _write(payload):
        path = tmp_path / "replacements.json"
        path.write_text(
            json.dumps(payload) if not isinstance(payload, str) else payload
        )
        return str(path)

    return _write


@pytest.mark.parametrize(
    "replacements, expected",
    [
        ([], []),
        ([{"find": "a", "replace": "b"}], [("a", "b")]),
        (
            [{"find": "a", "replace": "b"}, {"find": "c", "replace": "d"}],
            [("a", "b"), ("c", "d")],
        ),
    ],
)
def test_parses_find_and_replace_pairs(written, replacements, expected):
    parsed = parse_json(written({"replacements": replacements}))
    assert [(r.find, r.replace) for r in parsed] == expected


def test_key_path_defaults_when_absent(written):
    parsed = parse_json(written({"replacements": [{"find": "a", "replace": "b"}]}))
    assert parsed[0].key_path == Replacement.DEFAULT_KEY_PATH.split(".")


def test_key_path_is_honoured_when_given(written):
    path = "chunks.[].archives.[]"
    parsed = parse_json(
        written({"replacements": [{"find": "a", "replace": "b", "key_path": path}]})
    )
    assert parsed[0].key_path == path.split(".")


def test_unknown_keys_are_ignored(written):
    parsed = parse_json(
        written({"replacements": [{"find": "a", "replace": "b", "colour": "red"}]})
    )
    assert (parsed[0].find, parsed[0].replace) == ("a", "b")


@pytest.mark.parametrize(
    "entry",
    [
        {"find": "a"},  # no replacement
        {"replace": "b"},  # nothing to find
        {},  # neither
    ],
)
def test_incomplete_entries_raise_a_useful_error(written, entry):
    path = written({"replacements": [entry]})
    with pytest.raises(ValueError) as excinfo:
        parse_json(path)
    # The message should name the file and show the offending entry.
    assert path in str(excinfo.value)
    assert str(entry) in str(excinfo.value)


def test_missing_replacements_key_raises(written):
    with pytest.raises(KeyError):
        parse_json(written({"not_replacements": []}))


def test_invalid_json_raises(written):
    with pytest.raises(json.JSONDecodeError):
        parse_json(written("{not json"))
