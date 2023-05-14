from copy import deepcopy
from datetime import datetime

import pytz
from Cryptodome.Hash import SHA256
from galacteek.ld import asyncjsonld

from .jws import sign_jws, verify_jws


async def normalize_jsonld(jld_document):
    """
    Normalize and hash the json-ld document
    """
    options = {'algorithm': 'URDNA2015', 'format': 'application/nquads'}
    normalized = await asyncjsonld.normalize(jld_document, options=options)
    normalized_hash = SHA256.new(data=normalized.encode('utf-8')).digest()
    return normalized_hash


async def sign(jld_document, private_key):
    """
    Produces a signed JSON-LD document with a Json Web Signature
    """
    jld_document = deepcopy(jld_document)
    normalized_jld_hash = await normalize_jsonld(jld_document)
    jws_signature = sign_jws(normalized_jld_hash, private_key)

    # construct the signature document and add it to jsonld
    signature = {
        'type': 'RsaSignatureSuite2017',
        'created': datetime.now(tz=pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'signatureValue': jws_signature.decode('utf-8')
    }
    jld_document.update({'signature': signature})

    return jld_document


async def signsa(jld_document, private_key):
    jld_document = deepcopy(jld_document)
    normalized_jld_hash = await normalize_jsonld(jld_document)
    jws_signature = sign_jws(normalized_jld_hash, private_key)

    # construct the signature document and add it to jsonld
    signature = {
        'type': 'RsaSignatureSuite2017',
        'created': datetime.now(tz=pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'signatureValue': jws_signature.decode('utf-8')
    }

    return signature


async def verify(signed_jld_document, public_key):
    """
    Verifies the Json Web Signature of a signed JSON-LD Document
    """
    signed_jld_document = deepcopy(signed_jld_document)
    signature = signed_jld_document.pop('signature')
    jws_signature = signature['signatureValue'].encode('utf-8')
    normalized_jld_hash = await normalize_jsonld(signed_jld_document)

    return verify_jws(normalized_jld_hash, jws_signature, public_key)


async def verifysa(jld_document, jws_signature_value: str, public_key):
    normalized_jld_hash = await normalize_jsonld(deepcopy(jld_document))

    return verify_jws(
        normalized_jld_hash,
        jws_signature_value.encode('utf-8'),
        public_key
    )
