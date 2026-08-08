"""Compile every bundled version's .proto files into one descriptor archive.

Rather than generating a Python module per schema per version, this asks protoc
for the FileDescriptorSet directly and stores the descriptors themselves. See
keynote_parser/versions/archive.py for the reasoning and the format.
"""

import glob
import hashlib
import json
import logging
import lzma
import os
import pathlib
import subprocess
import tempfile

from google.protobuf import descriptor_pb2

from keynote_parser.versions.archive import ARCHIVE_FILENAME, MAGIC

COMPRESSION_PRESET = 9 | lzma.PRESET_EXTREME


def descriptors_for(protoc: str, proto_directory: str) -> dict[str, bytes]:
    """Run protoc over a version's protos and return {filename: serialized}."""
    with tempfile.NamedTemporaryFile(suffix=".pb") as out:
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
        file_set = descriptor_pb2.FileDescriptorSet()
        file_set.ParseFromString(pathlib.Path(out.name).read_bytes())

    return {f.name: f.SerializeToString() for f in file_set.file}


def registry_for(proto_directory: str) -> dict:
    """Read a version's TSP type registry, which lives beside its protos."""
    path = os.path.join(proto_directory, "registry.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} is missing. It records the type-id-to-message-name registry "
            "extracted from Keynote, and cannot be derived from the .proto files."
        )
    return json.loads(pathlib.Path(path).read_text())


def build(protoc: str, repo_root: str) -> str:
    versions = {}
    unique: dict[str, bytes] = {}
    first_seen: dict[str, str] = {}

    for proto_directory in sorted(
        glob.glob(os.path.join(repo_root, "protos", "versions", "*"))
    ):
        version = os.path.basename(proto_directory)
        descriptors = descriptors_for(protoc, proto_directory)

        files = {}
        for filename, serialized in descriptors.items():
            digest = hashlib.sha256(serialized).hexdigest()[:16]
            unique.setdefault(digest, serialized)
            first_seen.setdefault(digest, filename)
            files[filename] = digest

        versions[version] = {
            "files": files,
            "registry": registry_for(proto_directory),
        }
        logging.info(f"  {version}: {len(files)} schemas")

    # Order the blob by originating filename so that the same schema from
    # different Keynote versions - usually near-identical - sits adjacent and
    # compresses against its neighbours. This is worth more than it sounds:
    # ordering alone takes the compressed payload from ~0.4 MB to ~0.1 MB.
    order = sorted(unique, key=lambda d: (first_seen[d], d))

    blob = bytearray()
    spans = {}
    for digest in order:
        serialized = unique[digest]
        spans[digest] = [len(blob), len(serialized)]
        blob += serialized

    header = json.dumps(
        {"descriptors": spans, "versions": versions}, separators=(",", ":")
    ).encode()
    compressed_header = lzma.compress(header, preset=COMPRESSION_PRESET)
    compressed_blob = lzma.compress(bytes(blob), preset=COMPRESSION_PRESET)

    target = os.path.join(repo_root, "keynote_parser", "versions", ARCHIVE_FILENAME)
    with open(target, "wb") as f:
        f.write(MAGIC)
        f.write(len(compressed_header).to_bytes(4, "big"))
        f.write(compressed_header)
        f.write(compressed_blob)

    logging.info(
        f"Wrote {target}: {len(unique)} unique schemas across {len(versions)} "
        f"versions, {len(blob) / 1048576:.2f} MB -> "
        f"{os.path.getsize(target) / 1048576:.2f} MB"
    )
    return target
