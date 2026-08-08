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
import platform
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from contextlib import contextmanager
from typing import Generator

from rich.logging import RichHandler

from dumper.extract_mapping import extract_mapping
from dumper.generate_mapping import generate_mapping
from dumper.rename_proto_files import rename_proto_files
from dumper.rewrite_descriptor_pool import (
    rewrite_descriptor_pool,
    write_pool_module,
)
from dumper.rewrite_imports import rewrite_imports

# NOTE: dumper.protodump is imported lazily, inside the --app-path branch. It
# depends on private Protobuf APIs that only exist in protobuf<4, and importing
# it at module scope would make the far more common "just recompile the
# checked-in .proto files" path fail on a modern protobuf too.

logging.basicConfig(
    level="NOTSET",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(markup=True)],
)

# The generated code we ship is tied to the protoc that produced it: protoc 25
# and newer embed a runtime version check that refuses to load under an older
# google.protobuf than the one they were built against. Pinning protoc here
# keeps `protobuf>=3.13.0` an honest floor for end users, and stops whichever
# protoc happens to be on $PATH (Homebrew ships a very new one) from silently
# producing gencode that the installed protobuf can't import.
PROTOC_VERSION = "21.9"

PROTOC_PLATFORMS = {
    ("Darwin", "arm64"): "osx-aarch_64",
    ("Darwin", "x86_64"): "osx-x86_64",
    ("Linux", "aarch64"): "linux-aarch_64",
    ("Linux", "x86_64"): "linux-x86_64",
}


def vendored_protoc(repo_root_directory: str) -> str:
    """Return a path to the pinned protoc, downloading it if necessary.

    Deliberately does not fall back to a protoc on $PATH: an unpinned protoc is
    how you end up with gencode that imports fine on the machine that built it
    and nowhere else.
    """
    protoc_directory = os.path.join(repo_root_directory, ".protoc", PROTOC_VERSION)
    protoc_path = os.path.join(protoc_directory, "bin", "protoc")
    if os.path.exists(protoc_path):
        return protoc_path

    key = (platform.system(), platform.machine())
    if key not in PROTOC_PLATFORMS:
        raise RuntimeError(
            f"No pinned protoc {PROTOC_VERSION} build is known for {key}. Install "
            f"protoc {PROTOC_VERSION} manually and pass --protoc."
        )

    url = (
        "https://github.com/protocolbuffers/protobuf/releases/download/"
        f"v{PROTOC_VERSION}/protoc-{PROTOC_VERSION}-{PROTOC_PLATFORMS[key]}.zip"
    )
    logging.info(f"Downloading protoc {PROTOC_VERSION} from {url}...")
    os.makedirs(protoc_directory, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".zip") as archive:
        with urllib.request.urlopen(url) as response:
            shutil.copyfileobj(response, archive)
        archive.flush()
        with zipfile.ZipFile(archive.name) as zf:
            zf.extractall(protoc_directory)
    os.chmod(protoc_path, 0o755)
    return protoc_path


@contextmanager
def unsigned_copy_of(app_path: str) -> Generator[str, None, None]:
    app_name = os.path.basename(app_path).replace(".app", "")
    unsigned_app_bundle_filename = f"{app_name}.unsigned.app"
    # The executable name may differ from the bundle name (e.g. "Keynote 2025.app" contains "Keynote")
    exe_name = plistlib.load(
        open(os.path.join(app_path, "Contents", "Info.plist"), "rb")
    )["CFBundleExecutable"]

    # Get the identity from the system, falling back to ad-hoc signing ("-")
    # which requires no certificate and is sufficient for LLDB to attach.
    logging.info("Getting codesigning identity...")
    identity_output = subprocess.check_output(
        ["security", "find-identity", "-v", "-p", "codesigning"]
    ).decode()
    identity = identity_output.split('"')[1] if '"' in identity_output else "-"
    logging.info(f"Resigning {app_path} with codesigning identity: {identity!r}")

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
                os.path.join(target, "Contents", "MacOS", exe_name),
            ]
        )
        # Resign the app with the local identity (or ad-hoc if none available):
        logging.info(f"Resigning {target} with codesigning identity: {identity!r}")
        subprocess.run(
            [
                "codesign",
                "--sign",
                identity,
                "--verbose",
                os.path.join(target, "Contents", "MacOS", exe_name),
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
    parser.add_argument(
        "--protoc",
        type=str,
        default=None,
        help=(
            f"Path to protoc. Defaults to a pinned protoc {PROTOC_VERSION}, "
            "downloaded into .protoc/ if not already present."
        ),
    )
    args = parser.parse_args()

    repo_root_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    protoc = args.protoc or vendored_protoc(repo_root_directory)
    logging.info(f"Using protoc: {protoc}")

    if args.app_path:
        logging.info(f"Running dumper on {args.app_path}...")

        # Imported here rather than at module scope: protodump depends on
        # private Protobuf APIs that were removed in protobuf 4, so importing it
        # would break the compile-only path on a modern protobuf.
        from dumper.protodump import extract_proto_files

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
                protoc,
                "--proto_path",
                version_directory,
                "--python_out",
                gencode_proto_output_directory,
            ]
            + glob.glob(os.path.join(version_directory, "*.proto")),
            check=True,
        )
        # Step 6: Touch init.py in the generated code directory.
        open(os.path.join(gencode_proto_output_directory, "__init__.py"), "w").close()

        # Step 7: Rewrite the imports in the generated code.
        package_prefix = (
            f"keynote_parser.versions.{python_identifier_version}.generated"
        )
        rewrite_imports(
            glob.glob(os.path.join(gencode_proto_output_directory, "*.py")),
            package_prefix,
        )

        # Step 8: Give this version its own descriptor pool. Without this every
        # version registers the same .proto filenames into the global default
        # pool, so importing a second version fails with "duplicate file name".
        write_pool_module(gencode_proto_output_directory)
        rewrite_descriptor_pool(
            glob.glob(os.path.join(gencode_proto_output_directory, "*.py")),
            package_prefix,
        )

        logging.info(f"Dumped {version} to {gencode_proto_output_directory}.")
    logging.info("Done!")


if __name__ == "__main__":
    main()
