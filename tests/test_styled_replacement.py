"""Tests for character-index bookkeeping when replacing styled text.

Keynote stores which character style applies from which index. If a
replacement changes a run's length without shifting the indices after it, the
indices end up pointing past the end of the text - which, per the note in
replacement.py, makes Keynote render a text box 2^16 points tall and then
crash. So these assert the arithmetic, not just that a replacement happened.
"""

import pytest

from keynote_parser import codec
from keynote_parser.replacement import Replacement

MULTILINE_FILENAME = "./tests/data/multiline-oneslide.iwa"


def _styled_objects(data):
    """Every object carrying both text and more than one character style."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            entries = node.get("tableCharStyle", {}).get("entries")
            if entries and "text" in node and len(entries) > 1:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return found


@pytest.fixture
def styled():
    with open(MULTILINE_FILENAME, "rb") as f:
        data = codec.IWAFile.from_buffer(f.read(), MULTILINE_FILENAME).to_dict()
    objects = _styled_objects(data)
    assert objects, "fixture no longer contains multi-style text"
    return data


@pytest.mark.parametrize(
    "find, replace",
    [
        ("styles", "styles"),  # same length
        ("styles", "STYLE"),  # shorter
        ("styles", "much longer styles"),  # longer
        ("nothing-matches-this", "x"),  # no match at all
    ],
)
def test_style_indices_stay_within_the_text(styled, find, replace):
    replaced = Replacement(find, replace).perform_on(styled)

    for obj in _styled_objects(replaced):
        text_length = len(obj["text"][0])
        for entry in obj["tableCharStyle"]["entries"]:
            index = entry.get("characterIndex", 0)
            assert 0 <= index <= text_length, (
                f"characterIndex {index} outside text of length {text_length}"
            )


@pytest.mark.parametrize(
    "find, replace",
    [("styles", "STYLE"), ("styles", "much longer styles"), ("a", "aa")],
)
def test_style_indices_remain_sorted(styled, find, replace):
    replaced = Replacement(find, replace).perform_on(styled)

    for obj in _styled_objects(replaced):
        indices = [e.get("characterIndex", 0) for e in obj["tableCharStyle"]["entries"]]
        assert indices == sorted(indices), f"indices out of order: {indices}"


def test_replacement_actually_changes_the_text(styled):
    before = [o["text"][0] for o in _styled_objects(styled)]
    replaced = Replacement("styles", "STYLES").perform_on(styled)
    after = [o["text"][0] for o in _styled_objects(replaced)]

    assert before != after
    assert any("STYLES" in text for text in after)


def test_a_non_matching_replacement_leaves_indices_untouched(styled):
    before = [
        [e.get("characterIndex", 0) for e in o["tableCharStyle"]["entries"]]
        for o in _styled_objects(styled)
    ]
    replaced = Replacement("nothing-matches-this", "x").perform_on(styled)
    after = [
        [e.get("characterIndex", 0) for e in o["tableCharStyle"]["entries"]]
        for o in _styled_objects(replaced)
    ]
    assert before == after


def test_replaced_file_still_serializes(styled):
    replaced = Replacement("styles", "much longer styles").perform_on(styled)
    assert codec.IWAFile.from_dict(replaced).to_buffer()
