import argparse
import glob
import json
import os

RUNTIME_CODE = """

def collect_nested_message_types(message_type, name_class_map):
    # Messages nested inside other messages (i.e. TST.GroupByArchive.GroupNodeArchive)
    # are referenced by the TSP registry just like top-level ones, but don't appear in
    # DESCRIPTOR.message_types_by_name, so we have to walk into them explicitly.
    for nested_descriptor in message_type.DESCRIPTOR.nested_types:
        nested_type = getattr(message_type, nested_descriptor.name, None)
        if nested_type is None:
            # Map entry types (i.e. the synthetic FooEntry of a map<k, v> field)
            # have descriptors but no generated class; nothing to register.
            continue
        name_class_map[nested_type.DESCRIPTOR.full_name] = nested_type
        collect_nested_message_types(nested_type, name_class_map)


def compute_maps():
    name_class_map = {}
    for file in PROTO_FILES:
        for message_name in file.DESCRIPTOR.message_types_by_name:
            message_type = getattr(file, message_name)
            name_class_map[message_type.DESCRIPTOR.full_name] = message_type
            collect_nested_message_types(message_type, name_class_map)

    id_name_map = {}
    for k, v in list(TSPRegistryMapping.items()):
        if v in name_class_map:
            id_name_map[int(k)] = name_class_map[v]

    return name_class_map, id_name_map


NAME_CLASS_MAP, ID_NAME_MAP = compute_maps()
"""


def generate_mapping(mapping: dict[int, str], proto_dir: str) -> str:
    lines = []
    # Deliberately a repo-relative path: embedding __file__ would bake the
    # absolute path of whoever last ran the dumper into the generated output.
    generator = os.path.join("dumper", os.path.basename(__file__))
    lines.append(f"# Generated code! Edit {generator} instead.")
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
