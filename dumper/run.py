# /// script
# dependencies = [
#   "protobuf>=3.20.0rc1,<4",
#   "rich",
# ]
# ///
"""
Extract iWork protobufs from a .app bundle and dump them into
the appropriate locations in the keynote_parser directory tree.
"""

import argparse
import glob
import logging
import os
import plistlib
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Generator

from rich.logging import RichHandler

from dumper.extract_mapping import extract_mapping
from dumper.generate_mapping import generate_mapping
from dumper.protodump import extract_proto_files
from dumper.rename_proto_files import rename_proto_files
from dumper.rewrite_imports import rewrite_imports

logging.basicConfig(
    level="NOTSET",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(markup=True)],
)


@contextmanager
def unsigned_copy_of(app_path: str) -> Generator[str, None, None]:
    app_name = os.path.basename(app_path).replace(".app", "")
    unsigned_app_bundle_filename = f"{app_name}.unsigned.app"

    # Get the identity from the system:
    logging.info("Getting codesigning identity...")
    identity = subprocess.check_output(
        ["security", "find-identity", "-v", "-p", "codesigning"]
    ).decode()
    identity = identity.split('"')[1]
    if not identity:
        raise ValueError(
            "No codesigning identity found; please create one in Keychain Access first."
        )
    logging.info(f"Resigning {app_path} with local codesigning identity: {identity!r}")

    with tempfile.TemporaryDirectory() as temp_dir:
        target = os.path.join(temp_dir, unsigned_app_bundle_filename)
        logging.info(f"Copying {app_path} to {target}...")
        shutil.copytree(app_path, target)
        logging.info(f"Removing signature from {target}...")
        subprocess.run(
            [
                "codesign",
                "--remove-signature",
                "--verbose",
                os.path.join(target, "Contents", "MacOS", app_name),
            ]
        )
        # Resign the app with the local identity:
        logging.info(
            f"Resigning {target} with local codesigning identity: {identity!r}"
        )
        subprocess.run(
            [
                "codesign",
                "--sign",
                identity,
                "--verbose",
                os.path.join(target, "Contents", "MacOS", app_name),
            ]
        )
        logging.info(f"Successfully re-signed {target}.")
        yield target
        logging.info(f"Cleaning up {target}...")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--app-path",
        type=str,
        default=None,
        help="Path to the .app bundle. If not provided, only the proto compilation step will be done.",
    )
    args = parser.parse_args()

    repo_root_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if args.app_path:
        logging.info(f"Running dumper on {args.app_path}...")

        # Step 0: Get the version of the app to use as the output directory name.
        version_plist = plistlib.load(
            open(os.path.join(args.app_path, "Contents", "version.plist"), "rb")
        )
        version = version_plist["CFBundleShortVersionString"]
        bundle_version = version_plist["CFBundleVersion"]
        build_version = version_plist["ProductBuildVersion"]
        python_identifier_version = "v" + version.replace(".", "_")

        logging.info(f"Version: {version}")

        proto_output_directory = os.path.join(
            repo_root_directory, "protos", "versions", version
        )
        os.makedirs(proto_output_directory, exist_ok=True)

        # Remove the existing output directory if it exists.
        gencode_output_directory = os.path.join(
            repo_root_directory, "keynote_parser", "versions", python_identifier_version
        )
        os.makedirs(gencode_output_directory, exist_ok=True)

        logging.info(f"Proto output directory: {proto_output_directory}")
        # Step 1: Extract the protobuf files from the app bundle if we don't have them yet.
        if not glob.glob(os.path.join(proto_output_directory, "*.proto")):
            extract_proto_files(args.app_path, proto_output_directory)

        # Step 2: Extract the proto type mapping from the app bundle.
        if not os.path.exists(os.path.join(gencode_output_directory, "mapping.py")):
            with unsigned_copy_of(args.app_path) as temp_dir:
                mapping = extract_mapping(temp_dir)

            # Step 3: Generate the mapping.py file from the generated mapping.
            mapping_py_contents = generate_mapping(mapping, proto_output_directory)
            with open(os.path.join(gencode_output_directory, "mapping.py"), "w") as f:
                f.write(mapping_py_contents)
            with open(os.path.join(gencode_output_directory, "__init__.py"), "w") as f:
                f.write(
                    "from keynote_parser.macos_app_version import MacOSAppVersion\n\n"
                    f"VERSION = MacOSAppVersion({version!r}, {bundle_version!r}, {build_version!r})\n\n"
                )

            # Step 4: Rename the proto files:
            rename_proto_files(proto_output_directory)

    # Step 5: Run protoc on the proto files in each version directory:
    for version_directory in glob.glob(
        os.path.join(repo_root_directory, "protos", "versions", "*")
    ):
        version = os.path.basename(version_directory)
        python_identifier_version = "v" + version.replace(".", "_")
        gencode_version_directory = os.path.join(
            repo_root_directory, "keynote_parser", "versions", python_identifier_version
        )
        gencode_proto_output_directory = os.path.join(
            gencode_version_directory, "generated"
        )
        os.makedirs(gencode_proto_output_directory, exist_ok=True)
        subprocess.run(
            [
                "protoc",
                "--proto_path",
                version_directory,
                "--python_out",
                gencode_proto_output_directory,
            ]
            + glob.glob(os.path.join(version_directory, "*.proto")),
        )
        # Step 6: Touch init.py in the generated code directory.
        open(os.path.join(gencode_proto_output_directory, "__init__.py"), "w").close()

        # Step 7: Rewrite the imports in the generated code.
        rewrite_imports(
            glob.glob(os.path.join(gencode_proto_output_directory, "*.py")),
            f"keynote_parser.versions.{python_identifier_version}.generated",
        )

        logging.info(f"Dumped {version} to {gencode_proto_output_directory}.")
    logging.info("Done!")


if __name__ == "__main__":
    main()
