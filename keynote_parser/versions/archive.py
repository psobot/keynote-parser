"""Load Keynote's Protobuf schemas from a compressed archive of descriptor sets.

protoc's Python output wraps each schema in a module that embeds its serialized
FileDescriptorProto as a bytes literal. Every non-printable byte becomes a
four-character `\\xNN` escape, so the generated source runs about twice the size
of the data it carries - and with several Keynote versions bundled, most of
those files repeat between versions, because Apple often changes nothing in a
given schema from one release to the next.

Storing the descriptors themselves is far smaller. The archive is a plain
`.tar.xz` holding, for each bundled Keynote version, the FileDescriptorSet that
`protoc --descriptor_set_out` produces, plus one `registries.json` mapping each
version's TSP type ids to message names:

    $ tar tf keynote_parser/versions/protobuf_schemas.tar.xz
    10.2.desc
    11.2.desc
    ...
    registries.json
    $ tar xOf protobuf_schemas.tar.xz 14.5.desc | protoc --decode_raw | head

Nothing here is bespoke: `.desc` is protoc's own interchange format, and anyone
with tar, xz or protoc can take the archive apart without this library. Each
version is stored whole rather than deduplicated by hand, because xz's window
spans the entire payload - the schemas that repeat between versions collapse on
their own, and the result is marginally smaller than hand-deduplicating into a
custom container was.

Message classes are built from the resulting pool on demand. Each version gets
its own DescriptorPool: they all use the same .proto filenames, so sharing one
pool would collide on "duplicate file name".
"""

import json
import os
import tarfile
import threading

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

ARCHIVE_FILENAME = "protobuf_schemas.tar.xz"
ARCHIVE_PATH = os.path.join(os.path.dirname(__file__), ARCHIVE_FILENAME)

REGISTRIES_MEMBER = "registries.json"
DESCRIPTOR_SUFFIX = ".desc"

# Reentrant: pool_for() holds this while reading the archive, which takes it
# too. A plain Lock deadlocks the first time a pool is built.
_lock = threading.RLock()
_members = None
_registries = None
_pools = {}


def _read_archive():
    """Decompress the archive once per process."""
    global _members, _registries
    if _members is not None:
        return _members
    with _lock:
        if _members is not None:
            return _members
        members = {}
        with tarfile.open(ARCHIVE_PATH, "r:xz") as tar:
            for info in tar:
                if info.isfile():
                    members[info.name] = tar.extractfile(info).read()
        if REGISTRIES_MEMBER not in members:
            raise ValueError(
                f"{ARCHIVE_PATH} has no {REGISTRIES_MEMBER}. Rebuild it by "
                "running dumper/run.py."
            )
        _registries = {
            version: {int(k): v for k, v in registry.items()}
            for version, registry in json.loads(members[REGISTRIES_MEMBER]).items()
        }
        _members = members
        return _members


def bundled_versions():
    _read_archive()
    return sorted(_registries)


def registry_for(version: str) -> dict:
    """The TSP type registry - type id to message name - for one version."""
    _read_archive()
    try:
        return _registries[version]
    except KeyError:
        raise KeyError(f"No schemas bundled for Keynote {version}.") from None


def _descriptor_set(version: str) -> descriptor_pb2.FileDescriptorSet:
    members = _read_archive()
    member = version + DESCRIPTOR_SUFFIX
    if member not in members:
        raise KeyError(f"No schemas bundled for Keynote {version}.")
    file_set = descriptor_pb2.FileDescriptorSet()
    file_set.ParseFromString(members[member])
    return file_set


def pool_for(version: str) -> descriptor_pool.DescriptorPool:
    """Build (and cache) a DescriptorPool holding one version's schemas."""
    if version in _pools:
        return _pools[version]

    with _lock:
        if version in _pools:
            return _pools[version]

        protos = {proto.name: proto for proto in _descriptor_set(version).file}

        pool = descriptor_pool.DescriptorPool()

        # A fresh pool carries none of the well-known types, and these schemas
        # import descriptor.proto (TSP.FieldOptions extends FieldOptions).
        well_known = descriptor_pb2.FileDescriptorProto()
        descriptor_pb2.DESCRIPTOR.CopyToProto(well_known)
        pool.Add(well_known)

        # Add() requires a file's dependencies to already be present.
        added = set()

        def add(filename):
            if filename in added or filename not in protos:
                return
            added.add(filename)
            for dependency in protos[filename].dependency:
                add(dependency)
            pool.Add(protos[filename])

        for filename in protos:
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

    descriptors = {}
    for proto in _descriptor_set(version).file:
        file_descriptor = pool.FindFileByName(proto.name)
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
