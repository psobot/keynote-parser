# -*- coding: utf-8 -*-
import warnings

import pytest

from keynote_parser import bundle_utils
from keynote_parser.macos_app_version import MacOSAppVersion


def test_warn_on_old_version(capsys):
    dummy_version = MacOSAppVersion("9999.9", "10000.0.00", "9A000")
    with pytest.warns(bundle_utils.KeynoteVersionWarning):
        bundle_utils.warn_once_on_newer_keynote(installed_keynote_version=dummy_version)

    # Second call/import should not warn:
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        bundle_utils.warn_once_on_newer_keynote(installed_keynote_version=dummy_version)
