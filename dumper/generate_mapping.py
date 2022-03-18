import os
import json
import glob

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


def main():
    output_filename = "mapping.py"
    mapping_filename = "mapping.json"

    with open(output_filename, "w") as f:
        f.write(f"# Generated code! Edit {__file__} instead.\n")
        f.write("\n")

        f.write("from __future__ import absolute_import\n")
        f.write("\n")

        proto_files = sorted(
            [os.path.basename(path) for path in glob.glob(os.path.join("..", "protos", "*.proto"))]
        )

        for proto_file in proto_files:
            f.write(
                f"from .generated import {proto_file.replace('.proto', '')}_pb2 as"
                f" {proto_file.replace('.proto', '')}\n"
            )

        f.write("\n\n")

        f.write("PROTO_FILES = [\n")
        for proto_file in proto_files:
            f.write(f"\t{proto_file.replace('.proto', '')},\n")
        f.write("]\n")
        f.write("\n")

        with open(mapping_filename) as mapping_file:
            f.write(f"TSPRegistryMapping = {repr(json.load(mapping_file))}\n")

        f.write(RUNTIME_CODE)


if __name__ == "__main__":
    main()
