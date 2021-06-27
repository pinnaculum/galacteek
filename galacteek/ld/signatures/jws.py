import base64
import json

from Cryptodome.Hash import SHA256
from Cryptodome.PublicKey import RSA
from Cryptodome.Signature import PKCS1_v1_5


def b64safe_encode(payload):
    """
    b64 url safe encoding with the padding removed.
    """
    return base64.urlsafe_b64encode(payload).rstrip(b'=')


def b64safe_decode(payload):
    """
    b64 url safe decoding with the padding added.
    """
    return base64.urlsafe_b64decode(payload + b'=' * (4 - len(payload) % 4))


def normalize_json(payload):
    # TODO: Document why the json is normalized this way
    return json.dumps(payload,
                      separators=(',', ':'),
                      sort_keys=True).encode('utf-8')


def sign_jws(payload, private_key):
    # prepare payload to sign
    header = {'alg': 'RS256', 'b64': False, 'crit': ['b64']}
    normalized_json = normalize_json(header)
    encoded_header = b64safe_encode(normalized_json)
    prepared_payload = b'.'.join([encoded_header, payload])

    signature = sign_rs256(prepared_payload, private_key)
    encoded_signature = b64safe_encode(signature)
    jws_signature = b'..'.join([encoded_header, encoded_signature])

    return jws_signature


def verify_jws(payload, jws_signature, public_key):
    # remove the encoded header from the signature
    encoded_header, encoded_signature = jws_signature.split(b'..')
    signature = b64safe_decode(encoded_signature)
    payload = b'.'.join([encoded_header, payload])
    return verify_rs256(payload, signature, public_key)


def sign_rs256(payload, private_key):
    """
    Produce a RS256 signature of the payload
    """
    key = RSA.importKey(private_key)
    signer = PKCS1_v1_5.new(key)
    signature = signer.sign(SHA256.new(payload))
    return signature


def verify_rs256(payload, signature, public_key):
    """
    Verifies a RS256 signature
    """
    key = RSA.importKey(public_key)
    verifier = PKCS1_v1_5.new(key)
    return verifier.verify(SHA256.new(payload), signature)
