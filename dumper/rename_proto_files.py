import logging
import os
import sys
from glob import glob


def rename_proto_files(_dir):
    replacements = {}
    for proto_file in glob(os.path.join(_dir, "*.proto")):
        proto_file = os.path.basename(proto_file)
        no_ext = proto_file.replace(".proto", "")
        replaced = no_ext.replace(".", "_") + ".proto"
        replacements[proto_file] = replaced
        if proto_file != replaced:
            os.rename(os.path.join(_dir, proto_file), os.path.join(_dir, replaced))
            logging.info("Renamed %s to %s." % (proto_file, replaced))

    for proto_file in glob(os.path.join(_dir, "*.proto")):
        proto_file = os.path.basename(proto_file)
        original_contents = open(os.path.join(_dir, proto_file)).read()
        contents = original_contents
        for old, new in replacements.items():
            contents = contents.replace('import "%s";' % old, 'import "%s";' % new)
        if contents != original_contents:
            with open(os.path.join(_dir, proto_file), "w") as f:
                f.write(contents)
            logging.info("Updated %s." % proto_file)


if __name__ == "__main__":
    rename_proto_files(sys.argv[-1])
