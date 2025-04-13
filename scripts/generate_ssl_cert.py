from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta
import os

def generate_self_signed_cert():
    # Créer le dossier ssl s'il n'existe pas
    ssl_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ssl')
    if not os.path.exists(ssl_dir):
        os.makedirs(ssl_dir)

    # Générer une clé privée
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Créer un certificat auto-signé
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"CM"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Centre"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Yaounde"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Flow SMS"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"flowsms.cm"),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
        critical=False,
    ).sign(private_key, hashes.SHA256())

    # Sauvegarder la clé privée
    with open(os.path.join(ssl_dir, "private.key"), "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Sauvegarder le certificat
    with open(os.path.join(ssl_dir, "certificate.pem"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print("Certificat SSL auto-signé généré avec succès!")
    print(f"Clé privée: {os.path.join(ssl_dir, 'private.key')}")
    print(f"Certificat: {os.path.join(ssl_dir, 'certificate.pem')}")

if __name__ == "__main__":
    generate_self_signed_cert() 