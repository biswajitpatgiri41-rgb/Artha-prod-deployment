from app.security.authentication import hash_password, verify_password


LEGACY_PASSLIB_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$nrMW4hxjjJFSqtX6H0PoXQ$"
    "YMV3L4pnGMLQSumPOaTPctxWriC54/+bZS3Jp55AE20"
)


def test_native_argon2_hash_round_trip_and_wrong_password():
    encoded = hash_password("new-password-for-test")
    assert encoded.startswith("$argon2id$")
    assert verify_password("new-password-for-test", encoded)
    assert not verify_password("wrong-password", encoded)


def test_legacy_passlib_argon2_hash_remains_verifiable():
    assert verify_password("legacy-passlib-test", LEGACY_PASSLIB_HASH)


def test_malformed_password_hash_fails_closed():
    assert not verify_password("anything", "not-an-argon2-hash")
