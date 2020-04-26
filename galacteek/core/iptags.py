import re


def ipTag(tag, planet='Earth'):
    return '@{p}#{tag}'.format(p=planet, tag=tag)


ipTagRe = r'((?:@[\w]*)?\#[\w]+)'
ipTagReC = re.compile(ipTagRe)


def ipTagsRFind(query):
    return ipTagReC.findall(query)


def ipTagsFormat(tag: str, defaultPlanet=True):
    tag = tag.lstrip('#')

    if not tag.startswith('@'):
        if defaultPlanet:
            return ipTag(tag, planet='Earth')
        else:
            return '#' + tag
    else:
        return tag


def ipTagsFormatList(taglist: list, **kw):
    return [ipTagsFormat(tag, **kw) for tag in taglist]
