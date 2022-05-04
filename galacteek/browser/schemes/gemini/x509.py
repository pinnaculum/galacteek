from pathlib import Path
import datetime

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def x509SelfSignedGenerate(commonName,
                           orgName='Gemini Org',
                           unitName='Default CA Deployment',
                           monthsValid=12 * 40,
                           keyDestPath: Path = None,
                           certDestPath: Path = None):
    one_day = datetime.timedelta(1, 0, 0)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    public_key = private_key.public_key()
    builder = x509.CertificateBuilder()
    builder = builder.subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, commonName)
    ]))
    builder = builder.issuer_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, commonName),
    ]))
    builder = builder.not_valid_before(datetime.datetime.today() - one_day)
    builder = builder.not_valid_after(
        datetime.datetime.today() + datetime.timedelta(
            days=monthsValid * 30)
    )
    builder = builder.serial_number(x509.random_serial_number())
    builder = builder.public_key(public_key)
    certificate = builder.sign(
        private_key=private_key, algorithm=hashes.SHA256(),
        backend=default_backend()
    )

    if keyDestPath and certDestPath:
        with open(str(keyDestPath), "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        with open(certDestPath, "wb") as f:
            f.write(certificate.public_bytes(
                encoding=serialization.Encoding.PEM,
            ))

        return certDestPath, keyDestPath
    else:
        return None, None
