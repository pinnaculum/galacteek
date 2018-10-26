from jsontraverse.parser import JsonTraverseParser


class CTraverseParser(JsonTraverseParser):
    """
    Custom JsonTraverseParser (from json-traverse) that works directly on a
    preloaded object
    """

    def __init__(self, data):
        self.data = data


def traverseParser(data):
    return CTraverseParser(data)
