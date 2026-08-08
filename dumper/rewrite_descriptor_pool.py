"""Point a version's generated code at its own Protobuf descriptor pool.

protoc emits code that registers into `descriptor_pool.Default()`, which is
process-global and keyed by .proto filename. Every bundled Keynote version
compiles the same filenames - TSPMessages.proto, TSDArchives.proto and so on -
so importing a second version's mapping raised:

    TypeError: Couldn't build proto file into descriptor pool:
               duplicate file name TSDArchives.proto

That made the multi-version layout unusable for its stated purpose: only one
version could ever be loaded. Rewriting each version's generated modules to
share a pool of their own lets several coexist in one process.
"""

import argparse
import glob
import logging
import os

POOL_MODULE_NAME = "_descriptor_pool_for_version.py"

POOL_MODULE_TEMPLATE = '''\
"""Private Protobuf descriptor pool for one bundled version of Keynote.

Generated code! Edit dumper/rewrite_descriptor_pool.py instead.

Generated modules normally register into descriptor_pool.Default(), which is
global to the process and keyed by .proto filename. Every Keynote version
compiles the same filenames, so two versions sharing the default pool collide
with "duplicate file name". Each version gets its own pool instead.
"""

from google.protobuf import descriptor_pb2, descriptor_pool

POOL = descriptor_pool.DescriptorPool()

# A fresh pool does not carry the well-known types, and these schemas import
# google/protobuf/descriptor.proto (TSP.FieldOptions extends FieldOptions).
# Seed them from the default pool's copies.
for _well_known_descriptor in ({well_known}):
    _file_descriptor_proto = descriptor_pb2.FileDescriptorProto()
    _well_known_descriptor.CopyToProto(_file_descriptor_proto)
    POOL.Add(_file_descriptor_proto)
'''

# Anchor that protoc always emits, immediately after the google.protobuf imports.
IMPORT_ANCHOR = "# @@protoc_insertion_point(imports)"

DEFAULT_POOL_EXPRESSION = "_descriptor_pool.Default()"


def write_pool_module(generated_directory: str) -> str:
    """Write the module holding this version's pool, and return its path."""
    path = os.path.join(generated_directory, POOL_MODULE_NAME)
    with open(path, "w") as f:
        f.write(POOL_MODULE_TEMPLATE.format(well_known="descriptor_pb2.DESCRIPTOR,"))
    logging.info(f"Wrote {path}.")
    return path


def rewrite_descriptor_pool(files: list[str], package_prefix: str):
    """Rewrite generated modules to use their version's pool, not the default one."""
    pool_import = (
        f"from {package_prefix} import {POOL_MODULE_NAME[:-3]} as _version_pool"
    )

    for file in files:
        if os.path.basename(file) in (POOL_MODULE_NAME, "__init__.py"):
            continue

        with open(file) as f:
            content = f.read()

        if DEFAULT_POOL_EXPRESSION not in content:
            # Nothing registers from this module; leave it alone rather than
            # adding an import it does not use.
            continue

        content = content.replace(DEFAULT_POOL_EXPRESSION, "_version_pool.POOL")

        if IMPORT_ANCHOR not in content:
            raise ValueError(
                f"{file} has no {IMPORT_ANCHOR!r} anchor; protoc's output format "
                "has changed and this rewrite needs updating."
            )
        content = content.replace(IMPORT_ANCHOR, f"{IMPORT_ANCHOR}\n{pool_import}", 1)

        with open(file, "w") as f:
            f.write(content)
        logging.info(f"Pointed {os.path.basename(file)} at its version's pool.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("generated_directory")
    parser.add_argument("--package-prefix", required=True)
    args = parser.parse_args()

    write_pool_module(args.generated_directory)
    rewrite_descriptor_pool(
        glob.glob(os.path.join(args.generated_directory, "*.py")), args.package_prefix
    )


if __name__ == "__main__":
    main()
