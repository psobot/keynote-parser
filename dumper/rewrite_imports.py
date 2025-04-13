import argparse
import logging
import os
import re

REGEX = re.compile(r"^import (.*_pb2) as (.*__pb2)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument(
        "--package-prefix",
        help="Prefix to add to the generated package name",
        default="keynote_parser.generated",
    )
    args = parser.parse_args()

    rewrite_imports(args.files, args.package_prefix)


def rewrite_imports(files: list[str], package_prefix: str):
    for file in files:
        with open(file, "r") as f:
            content = f.read()

        new_content = []
        for line in content.splitlines():
            new_line = REGEX.sub(rf"import {package_prefix}.\1 as \2", line)
            if new_line != line:
                logging.info(f"Rewrote {os.path.basename(file)}: {line} -> {new_line}")
            new_content.append(new_line)
        with open(file, "w") as f:
            f.write("\n".join(new_content))


if __name__ == "__main__":
    main()
