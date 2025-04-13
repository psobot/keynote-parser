import importlib
import os

VERSIONS = []

for _dir in os.listdir(os.path.dirname(__file__)):
    if os.path.isdir(os.path.join(os.path.dirname(__file__), _dir)) and os.path.exists(
        os.path.join(os.path.dirname(__file__), _dir, "__init__.py")
    ):
        module = importlib.import_module(f".{_dir}", package="keynote_parser.versions")
        VERSIONS.append(module.VERSION)

LATEST_VERSION = max(VERSIONS)

__all__ = ["VERSIONS", "LATEST_VERSION"]
