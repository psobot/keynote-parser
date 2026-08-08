from __future__ import print_function
from __future__ import absolute_import

import os
import sys

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
import yaml

from contextlib import contextmanager

from PIL import Image
from io import BytesIO

from glob import glob
from tqdm import tqdm
from zipfile import ZipFile

from .codec import IWAFile
from .unicode_utils import fix_unicode


# Resolver.resolve() decides a scalar's implicit tag by running the resolver
# table's regexes against its value. It is a pure function of (value, implicit)
# for a fixed table, and PyYAML calls it once per scalar - 259,176 times for a
# single 320 KB .key file, because the YAML form of a document is ~30x the size
# of the .iwa it came from. Memoizing it produces byte-identical output.
#
# CDumper only replaces the emitter; the Representer and Resolver above it stay
# pure Python, which is why YAML dominates the profile even with libyaml
# installed.
_RESOLVE_CACHE_MAX_ENTRIES = 100_000


class MemoizingDumper(Dumper):
    _resolve_cache = {}

    def resolve(self, kind, value, implicit):
        if kind is not yaml.ScalarNode:
            return super().resolve(kind, value, implicit)
        key = (value, implicit)
        cached = self._resolve_cache.get(key)
        if cached is not None:
            return cached
        resolved = super().resolve(kind, value, implicit)
        # Bounded so a very large document can't grow this without limit.
        if len(self._resolve_cache) < _RESOLVE_CACHE_MAX_ENTRIES:
            self._resolve_cache[key] = resolved
        return resolved


def dump_yaml(data, stream=None):
    """Serialize an IWAFile's dict form to YAML, the one way we do it."""
    return yaml.dump(
        data,
        stream,
        default_flow_style=False,
        encoding="utf-8",
        Dumper=MemoizingDumper,
    )


def to_yaml_data(contents):
    """Accept either an IWAFile or a dict that has already been built from one.

    process_file hands the sink a plain dict when a replacement has already
    produced one, so that writing YAML doesn't have to round-trip it back
    through IWAFile.from_dict() and then to_dict() again.
    """
    return contents.to_dict() if isinstance(contents, IWAFile) else contents


def ensure_directory_exists(prefix, path):
    """Ensure that a path's directory exists."""
    parts = os.path.split(path)
    try:
        os.makedirs(os.path.join(*([prefix] + list(parts[:-1]))))
    except OSError:
        pass


def file_reader(path, progress=True):
    if path.endswith(".key"):
        return zip_file_reader(path, progress)
    else:
        return directory_reader(path, progress)


def zip_file_reader(path, progress=True):
    zipfile = ZipFile(path, "r")
    for _file in zipfile.filelist:
        _file.filename = _file.filename.encode("cp437").decode("utf-8")
    iterator = sorted(zipfile.filelist, key=lambda x: x.filename)
    if progress:
        iterator = tqdm(iterator)
    for zipinfo in iterator:
        if zipinfo.filename.endswith("/"):
            continue
        if progress:
            iterator.set_description("Reading {}...".format(zipinfo.filename))
        with zipfile.open(zipinfo) as handle:
            yield (zipinfo.filename, handle)


def directory_reader(path, progress=True):
    # Python <3.5 doesn't support glob with recursive, so this will have to do.
    iterator = set(sum([glob(path + ("/**" * i)) for i in range(10)], []))
    iterator = sorted(iterator)
    if progress:
        iterator = tqdm(iterator)
    for filename in iterator:
        if os.path.isdir(filename):
            continue
        rel_filename = filename.replace(path + "/", "")
        if progress:
            iterator.set_description("Reading {}...".format(rel_filename))
        with open(filename, "rb") as handle:
            yield (rel_filename, handle)


def file_sink(path, raw=False, subfile=None):
    if path == "-":
        if subfile:
            return cat_sink(subfile, raw)
        else:
            return ls_sink()
    if path.endswith(".key"):
        return zip_file_sink(path)
    return dir_file_sink(path, raw=raw)


@contextmanager
def dir_file_sink(target_dir, raw=False):
    def accept(filename, contents):
        ensure_directory_exists(target_dir, filename)
        target_path = os.path.join(target_dir, filename)
        is_iwa = isinstance(contents, (IWAFile, dict))
        if is_iwa and not raw:
            target_path += ".yaml"
        with open(target_path, "wb") as out:
            if is_iwa:
                if raw:
                    out.write(contents.to_buffer())
                else:
                    dump_yaml(to_yaml_data(contents), out)
            else:
                out.write(contents)

    accept.uses_stdout = False
    # Writing YAML needs the dict, not a rebuilt IWAFile.
    accept.needs_iwa_object = raw
    yield accept


@contextmanager
def ls_sink():
    def accept(filename, contents):
        print(filename)

    accept.uses_stdout = True
    # `ls` only ever prints names, so there is no reason to decode anything.
    accept.needs_iwa_contents = False
    yield accept


@contextmanager
def cat_sink(subfile, raw):
    def accept(filename, contents):
        if filename == subfile:
            if isinstance(contents, (IWAFile, dict)):
                if raw:
                    sys.stdout.buffer.write(contents.to_buffer())
                else:
                    print(dump_yaml(to_yaml_data(contents)).decode("ascii"))
            else:
                sys.stdout.buffer.write(contents)

    accept.uses_stdout = True
    accept.needs_iwa_object = raw
    yield accept


@contextmanager
def zip_file_sink(output_path):
    files_to_write = {}

    def accept(filename, contents):
        files_to_write[filename] = contents

    accept.uses_stdout = False
    # Writes binary .iwa back out, so it needs a real IWAFile to serialize.
    accept.needs_iwa_object = True

    yield accept

    print("Writing to %s..." % output_path)
    with ZipFile(output_path, "w") as zipfile:
        for filename, contents in tqdm(
            iter(list(files_to_write.items())), total=len(files_to_write)
        ):
            if isinstance(contents, IWAFile):
                zipfile.writestr(filename, contents.to_buffer())
            else:
                zipfile.writestr(filename, contents)


def process_file(filename, handle, sink, replacements=[], raw=False, on_replace=None):
    contents = None
    if ".iwa" in filename and not raw:
        if not getattr(sink, "needs_iwa_contents", True):
            # `ls` only prints names. Decoding every archive to throw the result
            # away made listing a document cost as much as parsing it.
            sink(filename.replace(".yaml", ""), None)
            return

        contents = handle.read()
        if filename.endswith(".yaml"):
            file = IWAFile.from_dict(
                yaml.load(fix_unicode(contents.decode("utf-8")), Loader=Loader)
            )
            filename = filename.replace(".yaml", "")
        else:
            file = IWAFile.from_buffer(contents, filename)

        file_has_changed = False
        for replacement in replacements:
            # Replacing in a file is expensive, so let's
            # avoid doing so if possible.
            if replacement.should_replace(file):
                file_has_changed = True
                break

        if file_has_changed:
            data = file.to_dict()
            for replacement in replacements:
                data = replacement.perform_on(data, on_replace=on_replace)
            if getattr(sink, "needs_iwa_object", True):
                sink(filename, IWAFile.from_dict(data))
            else:
                # A YAML sink is about to call to_dict() on whatever it is
                # given, so rebuilding an IWAFile from this dict only to take
                # it apart again is pure overhead.
                sink(filename, data)
        else:
            sink(filename, file)
        return

    if filename.startswith("Data/"):
        file_has_changed = False
        for replacement in replacements:
            find_parts = replacement.find.split(".")
            if len(find_parts) != 2:
                continue
            repl_filepart, repl_ext = find_parts
            data_filename = filename.replace("Data/", "")
            if data_filename.startswith(repl_filepart):
                # Scale this file to the appropriate size
                image = Image.open(handle)
                with open(replacement.replace, "rb") as f:
                    read_image = Image.open(f)
                    with BytesIO() as output:
                        read_image.thumbnail(image.size, Image.LANCZOS)
                        read_image.save(output, image.format)
                        sink(filename, output.getvalue())
                file_has_changed = True
                break

        if file_has_changed:
            return
    sink(filename, contents or handle.read())


def process(input_path, output_path, replacements=[], subfile=None, raw=False):
    completed_replacements = []

    def on_replace(replacement, old, new):
        completed_replacements.append((old, new))

    with file_sink(output_path, subfile=subfile) as sink:
        if not sink.uses_stdout:
            print("Reading from %s..." % input_path)
        for filename, handle in file_reader(input_path, not sink.uses_stdout):
            try:
                process_file(filename, handle, sink, replacements, raw, on_replace)
            except Exception as e:
                raise ValueError("Failed to process file %s due to: %s" % (filename, e))

    return completed_replacements
