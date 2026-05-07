from shared.auth.security import hash_password, verify_password
from shared.crypto.secrets import decode_secret, encode_secret, mask_secret


def test_password_hashing_roundtrip() -> None:
    hashed = hash_password("secret-value")
    assert verify_password("secret-value", hashed)
    assert not verify_password("wrong", hashed)


def test_secret_helpers() -> None:
    encoded = encode_secret("token-1234")
    assert decode_secret(encoded) == "token-1234"
    assert mask_secret("token-1234") == "to******34"
