import asyncio
import copy
import hashlib
import json
import random
import re


UPDATE_COMMAND = 'update'
VERIFY_COMMAND = 'verify'


class DataModel(object):
    """The common bit of the data structure."""

    def __init__(self):
        self.data = {}
        self.timestmap = 0

    def apply_delta(self, timestmap, delta):
        """Apply a diff to this data structure."""
        stack = list([([k], v) for k, v in delta.items()])
        for key, value in stack:
            if isinstance(value, dict):
                stack.extend([(key + [k], v) for k, v in value.items()])
            else:
                section = self.data
                for part in key[:-1]:
                    try:
                        section = section[part]
                    except KeyError:
                        section[part] = {}
                        section = section[part]
                section[key[-1]] = value
        self.timestmap = timestmap

    def reset(self, data, timestamp):
        """Reset this data structure ."""
        self.data = data
        self.timestmap = timestamp

    async def checksum(self):
        """Somewhat dicey way to get a checksum of the data structure.

        Returns:
            tuple - (timestmap, checksum)

        """
        return (
            self.timestmap,
            hashlib.sha256(json.dumps(self.data).encode()).hexdigest()
        )

    async def dump(self):
        return self.timestmap, copy.deepcopy(self.data)

    def pprint(self):
        print(json.dumps(self.data, indent=4))


def word_generator(min_len=4, max_len=8, skip=10):
    """Generate words from the dictionary in alphabetical order.

    Args:
        min_len (int): Minimum word length.
        max_len (int): Maximum word length.
        skip (int): Skip every Nth match to spice things up a little.

    Yields:
        string - A random word.

    """
    word_regex = re.compile(r'\w{%d,%d}\n' % (min_len, max_len))
    ind = 0
    with open('/usr/share/dict/words', 'r') as dictionary:
        for line in dictionary:
            if ind == skip:
                if word_regex.match(line):
                    yield line.strip()
                    ind = 0
            else:
                ind += 1


def delta_generator(commonality=0.5, depth=6):
    """Generate random additions / modifications to a nested dict.

    Args:
        commonality (float): Decimal likelihood of each new entry using a
            previously defined key (though not necessarily at the same level).
        depth (int): Odds against another level of nesting (1:N).

    Yields:
        dict - A nested dictionary containing only strings for keys and values.

    """
    keys = []
    words = word_generator()

    while True:
        flag = False
        key = []
        ret = {}
        while not flag:
            if keys and random.random() < commonality:
                new = random.choices(keys)[0]
            else:
                new = words.__next__()
                keys.append(new)
            key.append(new)

            if not id(new) % depth:
                value = {}
            else:
                value = words.__next__()
                flag = True

            section = ret
            for item in key[:-1]:
                section = section[item]
            section[key[-1]] = value

        yield ret
