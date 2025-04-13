# Copyright 2020-2025 Peter Sobot
"""Unpack and repack Apple Keyote files."""

__author__ = "Peter Sobot"

from keynote_parser.versions import VERSIONS

__major_version__ = 1
__patch_version__ = 0

__supported_keynote_version__ = max(VERSIONS)
__version_tuple__ = (
    __major_version__,
    __supported_keynote_version__.major,
    __supported_keynote_version__.minor,
    __patch_version__,
)
__version__ = ".".join([str(x) for x in __version_tuple__])

__email__ = "github@petersobot.com"
__description__ = "A tool for manipulating Apple Keynote presentation files."
__url__ = "https://github.com/psobot/keynote-parser"
__new_issue_url__ = "https://github.com/psobot/keynote-parser/issues/new"
