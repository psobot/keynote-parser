import argparse
import glob
import json
import os

RUNTIME_CODE = """

def compute_maps():
    name_class_map = {}
    for file in PROTO_FILES:
        for message_name in file.DESCRIPTOR.message_types_by_name:
            message_type = getattr(file, message_name)
            name_class_map[message_type.DESCRIPTOR.full_name] = message_type

    id_name_map = {}
    for k, v in list(TSPRegistryMapping.items()):
        if v in name_class_map:
            id_name_map[int(k)] = name_class_map[v]

    return name_class_map, id_name_map


NAME_CLASS_MAP, ID_NAME_MAP = compute_maps()
"""


def generate_mapping(mapping: dict[int, str], proto_dir: str) -> str:
    lines = []
    lines.append(f"# Generated code! Edit {__file__} instead.")
    lines.append("")

    lines.append("from __future__ import absolute_import")

    proto_files = sorted(
        [
            os.path.basename(path)
            for path in glob.glob(os.path.join(proto_dir, "*.proto"))
        ]
    )

    proto_identifiers = sorted(
        set(
            [
                proto_file.replace(".proto", "").replace(".", "_")
                for proto_file in proto_files
            ]
        )
    )

    for identifier in proto_identifiers:
        lines.append(f"from .generated import {identifier}_pb2 as {identifier}")

    lines.append("\n")

    lines.append("PROTO_FILES = [")
    for identifier in proto_identifiers:
        lines.append(f"\t{identifier},")
    lines.append("]")
    lines.append("")

    lines.append(f"TSPRegistryMapping = {repr(mapping)}")

    lines.append(RUNTIME_CODE)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mapping_filename", type=str, help="Path to the mapping file.")
    parser.add_argument(
        "proto_dir",
        type=str,
        help="Path to a directory containing proto files referenced by the mapping.",
    )
    parser.add_argument(
        "output_filename",
        type=str,
        help="Path to the output file to write to. Will be overwritten.",
    )
    args = parser.parse_args()

    mapping = json.load(open(args.mapping_filename))
    with open(args.output_filename, "w") as f:
        f.write(generate_mapping(mapping, args.proto_dir))


if __name__ == "__main__":
    main()
