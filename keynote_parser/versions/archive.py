"""Load Keynote's Protobuf schemas from a compressed descriptor archive.

protoc's Python output wraps each schema in a module that embeds its serialized
FileDescriptorProto as a bytes literal. Every non-printable byte becomes a
four-character `\\xNN` escape, so the generated source runs about twice the size
of the data it carries - and with several Keynote versions bundled, over half
of those files are byte-for-byte identical between versions, because Apple
often changes nothing in a given schema from one release to the next.

Storing the descriptors themselves instead, deduplicated and compressed
together, is both far smaller and slightly faster to load than importing the
equivalent generated modules. It also makes each additional bundled version
nearly free, which matters because the alternative gets worse every release.

The archive holds:
  - every distinct FileDescriptorProto, concatenated in a stable order so that
    near-identical schemas sit adjacent and compress against each other
  - an index mapping each bundled Keynote version to the descriptors it uses,
    and each descriptor to its span within the blob
  - each version's TSP type registry (type id -> message name)

Message classes are built from the resulting pool on demand. Each version gets
its own DescriptorPool: they all use the same .proto filenames, so sharing one
pool would collide on "duplicate file name".
"""

import json
import lzma
import os
import threading

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

# ".kpda" - Keynote Parser Descriptor Archive - rather than a generic ".bin",
# and deliberately not ".xz": this is a container with its own header, not a
# bare LZMA stream, so naming it after the compressor would mislead anyone who
# tried to decompress it directly. The extension matches the magic bytes below.
ARCHIVE_FILENAME = "protobuf_schemas.kpda"
ARCHIVE_PATH = os.path.join(os.path.dirname(__file__), ARCHIVE_FILENAME)

# The archive stores a compressed JSON header followed by the compressed blob.
# Both are length-prefixed so the header can be read without the payload.
MAGIC = b"KPDA\x01"

# Reentrant: pool_for() holds this while calling _read_archive(), which takes
# it too. A plain Lock deadlocks the first time a pool is built.
_lock = threading.RLock()
_archive = None
_pools = {}
_registries = {}


def _read_archive():
    """Decompress the archive once per process."""
    global _archive
    if _archive is not None:
        return _archive
    with _lock:
        if _archive is not None:
            return _archive
        with open(ARCHIVE_PATH, "rb") as f:
            raw = f.read()
        if not raw.startswith(MAGIC):
            raise ValueError(
                f"{ARCHIVE_PATH} is not a keynote-parser descriptor archive. "
                "Rebuild it by running dumper/run.py."
            )
        offset = len(MAGIC)
        header_length = int.from_bytes(raw[offset : offset + 4], "big")
        offset += 4
        header = json.loads(lzma.decompress(raw[offset : offset + header_length]))
        offset += header_length
        _archive = (header, lzma.decompress(raw[offset:]))
        return _archive


def bundled_versions():
    return sorted(_read_archive()[0]["versions"])


def registry_for(version: str) -> dict:
    """The TSP type registry - type id to message name - for one version."""
    if version not in _registries:
        header, _ = _read_archive()
        try:
            entry = header["versions"][version]
        except KeyError:
            raise KeyError(f"No schemas bundled for Keynote {version}.") from None
        _registries[version] = {int(k): v for k, v in entry["registry"].items()}
    return _registries[version]


def pool_for(version: str) -> descriptor_pool.DescriptorPool:
    """Build (and cache) a DescriptorPool holding one version's schemas."""
    if version in _pools:
        return _pools[version]

    with _lock:
        if version in _pools:
            return _pools[version]

        header, blob = _read_archive()
        try:
            files = header["versions"][version]["files"]
        except KeyError:
            raise KeyError(f"No schemas bundled for Keynote {version}.") from None
        spans = header["descriptors"]

        def serialized(filename):
            start, length = spans[files[filename]]
            return blob[start : start + length]

        pool = descriptor_pool.DescriptorPool()

        # A fresh pool carries none of the well-known types, and these schemas
        # import descriptor.proto (TSP.FieldOptions extends FieldOptions).
        well_known = descriptor_pb2.FileDescriptorProto()
        descriptor_pb2.DESCRIPTOR.CopyToProto(well_known)
        pool.Add(well_known)

        # AddSerializedFile requires a file's dependencies to be present first.
        parsed = {}
        for filename in files:
            proto = descriptor_pb2.FileDescriptorProto()
            proto.ParseFromString(serialized(filename))
            parsed[filename] = proto

        added = set()

        def add(filename):
            if filename in added or filename not in parsed:
                return
            added.add(filename)
            for dependency in parsed[filename].dependency:
                add(dependency)
            pool.AddSerializedFile(serialized(filename))

        for filename in files:
            add(filename)

        _pools[version] = pool
        return pool


def _walk(descriptor, into):
    into[descriptor.full_name] = descriptor
    for nested in descriptor.nested_types:
        _walk(nested, into)


def compute_maps(version: str):
    """Return (ID_NAME_MAP, NAME_CLASS_MAP) for one bundled Keynote version.

    Nested messages are walked explicitly: the TSP registry refers to them the
    same way it refers to top-level ones, but they don't appear in a file's
    message_types_by_name.
    """
    pool = pool_for(version)
    header, _ = _read_archive()

    descriptors = {}
    for filename in header["versions"][version]["files"]:
        file_descriptor = pool.FindFileByName(filename)
        for message_descriptor in file_descriptor.message_types_by_name.values():
            _walk(message_descriptor, descriptors)

    name_class_map = {
        name: message_factory.GetMessageClass(descriptor)
        for name, descriptor in descriptors.items()
    }
    id_name_map = {
        type_id: name_class_map[name]
        for type_id, name in registry_for(version).items()
        if name in name_class_map
    }
    return id_name_map, name_class_map


def message_class(version: str, full_name: str):
    """A single message class, by Protobuf full name."""
    return message_factory.GetMessageClass(
        pool_for(version).FindMessageTypeByName(full_name)
    )
