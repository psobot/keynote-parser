"""Tests for the surrogate-pair helpers in unicode_utils.

fix_unicode runs over every byte of YAML on the way in, so a mistake here
corrupts text silently rather than raising. from_surrogate_pair and
to_surrogate_pair had no direct coverage at all.
"""

import pytest

from keynote_parser.unicode_utils import (
    fix_unicode,
    from_surrogate_pair,
    to_py3_compatible,
    to_surrogate_pair,
)


@pytest.mark.parametrize(
    "high, low, codepoint",
    [
        ("D83C", "DDE8", 0x1F1E8),  # regional indicator C
        ("D83C", "DDE6", 0x1F1E6),  # regional indicator A
        ("D83D", "DE00", 0x1F600),  # grinning face
        ("D800", "DC00", 0x10000),  # first non-BMP codepoint
        ("DBFF", "DFFF", 0x10FFFF),  # last valid codepoint
    ],
)
def test_surrogate_pair_decoding(high, low, codepoint):
    assert from_surrogate_pair(high, low) == codepoint


@pytest.mark.parametrize("codepoint", ["10000", "1F1E8", "1F600", "10FFFF", "1D11E"])
def test_surrogate_pair_encoding_round_trips(codepoint):
    high, low = to_surrogate_pair(codepoint)
    assert from_surrogate_pair(format(high, "x"), format(low, "x")) == int(
        codepoint, 16
    )


@pytest.mark.parametrize("case", ["lower", "upper", "mixed"])
def test_hex_case_does_not_matter(case):
    pair = {
        "lower": r"\ud83c\udde8",
        "upper": r"\uD83C\uDDE8",
        "mixed": r"\uD83c\udDE8",
    }
    assert to_py3_compatible(pair[case]) == r"\U0001f1e8"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "plain ascii",
        r"српска",  # Cyrillic, all BMP
        "✖️",  # already-decoded characters
        r"\ud83c",  # a lone high surrogate
        r"\udde8",  # a lone low surrogate
        r"\udde8\ud83c",  # a pair in the wrong order
        r"\u0041\u0042",  # two BMP escapes that must not be merged
    ],
)
def test_text_without_valid_surrogate_pairs_is_untouched(text):
    assert to_py3_compatible(text) == text
    assert fix_unicode(text) == text


@pytest.mark.parametrize(
    "text, expected",
    [
        (r"\ud83c\udde8\ud83c\udde6", r"\U0001f1e8\U0001f1e6"),
        (r"before \ud83d\ude00 after", r"before \U0001f600 after"),
        (r"\ud83d\ude00\ud83d\ude00", r"\U0001f600\U0001f600"),
    ],
)
def test_valid_pairs_are_converted(text, expected):
    assert to_py3_compatible(text) == expected
    assert fix_unicode(text) == expected


def test_conversion_is_idempotent():
    once = to_py3_compatible(r"\ud83c\udde8\ud83c\udde6")
    assert to_py3_compatible(once) == once
