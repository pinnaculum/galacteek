from copy import deepcopy
from datetime import datetime

import pytz
from Crypto.Hash import SHA256
from pyld import jsonld

from .jws import sign_jws, verify_jws


def normalize_jsonld(jld_document):
    """
    Normalize and hash the json-ld document
    """
    options = {'algorithm': 'URDNA2015', 'format': 'application/nquads'}
    normalized = jsonld.normalize(jld_document, options=options)
    normalized_hash = SHA256.new(data=normalized.encode('utf-8')).digest()
    return normalized_hash


def sign(jld_document, private_key):
    """
    Produces a signed JSON-LD document with a Json Web Signature
    """
    jld_document = deepcopy(jld_document)
    normalized_jld_hash = normalize_jsonld(jld_document)
    jws_signature = sign_jws(normalized_jld_hash, private_key)

    # construct the signature document and add it to jsonld
    signature = {
        'type': 'RsaSignatureSuite2017',
        'created': datetime.now(tz=pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'signatureValue': jws_signature.decode('utf-8')
    }
    jld_document.update({'signature': signature})

    return jld_document


def verify(signed_jld_document, public_key):
    """
    Verifies the Json Web Signature of a signed JSON-LD Document
    """
    signed_jld_document = deepcopy(signed_jld_document)
    signature = signed_jld_document.pop('signature')
    jws_signature = signature['signatureValue'].encode('utf-8')
    normalized_jld_hash = normalize_jsonld(signed_jld_document)

    return verify_jws(normalized_jld_hash, jws_signature, public_key)
