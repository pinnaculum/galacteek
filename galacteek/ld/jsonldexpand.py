from yarl import URL


class ExpandedJSONLDQuerier:
    def __init__(self, ex):
        self._data = ex

    def u(self, uri):
        try:
            r = self._data[uri]
            if isinstance(r, list):
                val = r.pop(0)
                assert isinstance(val, dict)
                return val['@value']
        except Exception:
            return None

    def gu(self, _id, attr):
        uri = URL.build(
            host='galacteek.ld',
            scheme='ips',
            path=f'/{_id}',
            fragment=attr
        )
        return self.u(str(uri))
