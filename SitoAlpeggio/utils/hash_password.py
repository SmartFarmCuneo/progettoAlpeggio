import hashlib


def hash_password(psw):
    return hashlib.sha256(psw.encode()).hexdigest()
