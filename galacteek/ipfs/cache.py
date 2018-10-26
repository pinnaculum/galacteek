import collections


class IPFSEntryCache(object):
    def __init__(self):
        self.reset()

    def reset(self):
        self._cache = collections.OrderedDict()

    def register(self, entry):
        if entry['Hash'] not in self._cache:
            self._cache[entry['Hash']] = entry

    def __contains__(self, oHash):
        return oHash in self._cache

    def purge(self, oHash):
        if oHash in self:
            del self._cache[oHash]

    def getByType(self, etype):
        entries = {}
        for ohash, entry in self._cache.items():
            if entry['Type'] == etype:
                entries[ohash] = entry
        return entries
