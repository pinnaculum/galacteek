import bcp47


def mainLangTags():
    tags = {}

    for tag, name in bcp47.tags.items():
        if '-' not in tag:
            tags[tag] = name

    return tags
