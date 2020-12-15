import re

bmAddrRe = re.compile(r'^(BM-[a-zA-Z0-9]{34,36})$')
bmNbEmailAddrRe = re.compile(r'^(BM-[a-zA-Z0-9]{34,36})@bitmessage$')


def bmAddressValid(addr):
    return bmAddrRe.match(addr)


def bmAddressExtract(email):
    ma = bmNbEmailAddrRe.match(email)
    if ma:
        return ma.group(1)
