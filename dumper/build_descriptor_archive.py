"""Compile every bundled version's .proto files into one descriptor archive.

Rather than generating a Python module per schema per version, this asks protoc
for each version's FileDescriptorSet and tars them up with xz. See
keynote_parser/versions/archive.py for the format and the reasoning.
"""

import glob
import io
import json
import logging
import lzma
import os
import pathlib
import subprocess
import tarfile
import tempfile

from keynote_parser.versions.archive import (
    ARCHIVE_FILENAME,
    DESCRIPTOR_SUFFIX,
    REGISTRIES_MEMBER,
)

COMPRESSION_PRESET = 9 | lzma.PRESET_EXTREME


def descriptor_set_for(protoc: str, proto_directory: str) -> bytes:
    """Run protoc over a version's protos and return its FileDescriptorSet."""
    with tempfile.NamedTemporaryFile(suffix=".desc") as out:
        subprocess.run(
            [
                protoc,
                "--proto_path",
                proto_directory,
                "--descriptor_set_out",
                out.name,
                *sorted(glob.glob(os.path.join(proto_directory, "*.proto"))),
            ],
            check=True,
        )
        return pathlib.Path(out.name).read_bytes()


def registry_for(proto_directory: str) -> dict:
    """Read a version's TSP type registry, which lives beside its protos."""
    path = os.path.join(proto_directory, "registry.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} is missing. It records the type-id-to-message-name registry "
            "extracted from Keynote, and cannot be derived from the .proto files."
        )
    return json.loads(pathlib.Path(path).read_text())


def _add(tar: tarfile.TarFile, name: str, data: bytes):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    # Fixed metadata so the archive is reproducible: the same inputs and the
    # same protoc should always produce the same bytes.
    info.mtime = 0
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    tar.addfile(info, io.BytesIO(data))


def build(protoc: str, repo_root: str) -> str:
    descriptor_sets, registries = {}, {}

    for proto_directory in sorted(
        glob.glob(os.path.join(repo_root, "protos", "versions", "*"))
    ):
        version = os.path.basename(proto_directory)
        descriptor_sets[version] = descriptor_set_for(protoc, proto_directory)
        registries[version] = registry_for(proto_directory)
        logging.info(
            f"  {version}: {len(descriptor_sets[version]) / 1024:.0f} KB of "
            f"descriptors, {len(registries[version])} registry entries"
        )

    target = os.path.join(repo_root, "keynote_parser", "versions", ARCHIVE_FILENAME)
    # Versions are written whole and in order: xz's window spans the payload, so
    # the schemas that repeat between versions compress against each other
    # without needing to be deduplicated here.
    with tarfile.open(target, "w:xz", preset=COMPRESSION_PRESET) as tar:
        for version in sorted(descriptor_sets):
            _add(tar, version + DESCRIPTOR_SUFFIX, descriptor_sets[version])
        _add(
            tar,
            REGISTRIES_MEMBER,
            json.dumps(registries, separators=(",", ":"), sort_keys=True).encode(),
        )

    raw = sum(len(d) for d in descriptor_sets.values())
    logging.info(
        f"Wrote {target}: {len(descriptor_sets)} versions, "
        f"{raw / 1048576:.2f} MB of descriptors -> "
        f"{os.path.getsize(target) / 1048576:.2f} MB"
    )
    return target
