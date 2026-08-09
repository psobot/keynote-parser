"""Schema maps for Keynote 12.2.1, loaded from the shared descriptor archive."""

from keynote_parser.versions.archive import compute_maps, registry_for

VERSION_STRING = "12.2.1"

TSPRegistryMapping = registry_for(VERSION_STRING)
ID_NAME_MAP, NAME_CLASS_MAP = compute_maps(VERSION_STRING)
