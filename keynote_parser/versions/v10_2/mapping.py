"""Schema maps for Keynote 10.2, loaded from the shared descriptor archive."""

from keynote_parser.versions.archive import compute_maps, registry_for

VERSION_STRING = "10.2"

TSPRegistryMapping = registry_for(VERSION_STRING)
ID_NAME_MAP, NAME_CLASS_MAP = compute_maps(VERSION_STRING)
