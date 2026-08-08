import re
from functools import total_ordering

_DIGIT_RUN = re.compile(r"(\d+)")


def _natural_key(value):
    """Split a version-ish string into a tuple that sorts the way a human reads it.

    Apple's version strings interleave numbers and letters ("7043.0.93",
    "1A89s"), and comparing them as plain strings gets the numeric parts wrong
    as soon as they differ in length: "1A107s" < "1A89s" is True, because "1"
    sorts before "8". Splitting on digit runs and comparing those numerically
    gives 107 > 89, which is what's meant.
    """
    parts = _DIGIT_RUN.split(value or "")
    # Tag each element so ints never compare against strs on Python 3.
    return tuple(
        (0, int(part), "") if part.isdigit() else (1, 0, part)
        for part in parts
        if part != ""
    )


@total_ordering
class MacOSAppVersion:
    def __init__(self, short_version_string, bundle_version, build_version):
        self.short_version_string = short_version_string
        self.short_version_tuple = [int(x) for x in short_version_string.split(".")]
        self.bundle_version = bundle_version
        self.build_version = build_version

    def __str__(self):
        return "%s (%s, %s)" % (
            self.short_version_string,
            self.bundle_version,
            self.build_version,
        )

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self)

    @property
    def _comparison_key(self):
        """Order by short version first, then bundle version, then build version.

        This has to be a single tuple rather than three separate comparisons.
        The previous implementation OR'd them together, which meant a version
        could compare less-than another in both directions at once: 14.4 and
        14.5 each sorted below the other, because "1A107s" < "1A89s" as strings.
        max() over a list of versions then depended on iteration order, and
        VERSIONS is built from os.listdir().
        """
        return (
            tuple(self.short_version_tuple),
            _natural_key(self.bundle_version),
            _natural_key(self.build_version),
        )

    def __eq__(self, other):
        if not isinstance(other, MacOSAppVersion):
            return NotImplemented
        return self._comparison_key == other._comparison_key

    def __hash__(self):
        return hash(self._comparison_key)

    def __lt__(self, other):
        if not isinstance(other, MacOSAppVersion):
            raise TypeError(
                "< not supported between MacOSAppVersion and %s" % type(other)
            )
        return self._comparison_key < other._comparison_key

    @property
    def major(self):
        return self.short_version_tuple[0]

    @property
    def minor(self):
        return self.short_version_tuple[1]
