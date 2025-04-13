import argparse
import re

REGEX = re.compile(r"^import (.*_pb2) as (.*__pb2)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    for file in args.files:
        with open(file, "r") as f:
            content = f.read()

        new_content = []
        for line in content.splitlines():
            new_line = REGEX.sub(r"import keynote_parser.generated.\1 as \2", line)
            if new_line != line:
                print(f"Rewrote {file}: {line} -> {new_line}")
            new_content.append(new_line)
        with open(file, "w") as f:
            f.write("\n".join(new_content))


if __name__ == "__main__":
    main()
