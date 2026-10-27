"""Offline checks for setting precedence, secret redaction, and invalid config."""

import json

import pytest

from scripts.check_environment import (
    Check,
    check_firebase_credentials,
    check_openai_key,
    check_public_settings,
    exit_status,
    is_valid_address,
    read_environment,
)


def test_process_settings_override_file_including_explicit_blanks(tmp_path):
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=from-file\nAPI_BASE_URL=https://api.example.com\n", encoding="utf-8")
    values = read_environment(path, {"OPENAI_API_KEY": ""})
    assert values["OPENAI_API_KEY"] == ""
    assert values["API_BASE_URL"] == "https://api.example.com"


def test_dotenv_does_not_expand_secret_contents(tmp_path):
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY='keep-${SOME_VARIABLE}-literal'\n", encoding="utf-8")
    assert read_environment(path, {})["OPENAI_API_KEY"] == "keep-${SOME_VARIABLE}-literal"


@pytest.mark.parametrize("value", [
    "*", "http://localhost:5500/", "https://example.com/api", "https://example.com?key=secret",
    "https://name:secret@example.com", "http://example.com", "https://example.com:99999", "https://exa mple.com", "",
])
def test_invalid_origins_are_rejected_without_echoing_values(value):
    checks = check_public_settings({"ALLOWED_ORIGINS": value, "API_BASE_URL": "http://127.0.0.1:8000"})
    result = next(check for check in checks if check.name == "ALLOWED_ORIGINS")
    assert result.status != "PASS"
    if "secret" in value:
        assert "secret" not in repr(result)


@pytest.mark.parametrize("value", ["http://localhost:5500", "http://127.0.0.1:5500", "https://example.vercel.app"])
def test_valid_development_origins(value):
    assert is_valid_address(value, origin=True, production=False)


def test_production_requires_https():
    assert not is_valid_address("http://localhost:5500", origin=True, production=True)
    assert is_valid_address("https://api.example.com", origin=False, production=True)


def test_local_api_base_url_must_not_include_api_path():
    assert not is_valid_address("http://localhost:8000/api", origin=False, production=False)
    assert is_valid_address("http://localhost:8000/", origin=False, production=False)


def test_secret_value_is_not_in_check_results():
    secret = "unit-test-not-a-real-key-0123456789"
    result = check_openai_key({"OPENAI_API_KEY": secret})
    assert result.status == "PASS"
    assert secret not in repr(result)
    assert check_openai_key({}).status == "MISSING"


def test_conflicting_credentials_are_rejected_before_reading_files():
    result = check_firebase_credentials({"FIREBASE_SERVICE_ACCOUNT_JSON": "sensitive-json", "FIREBASE_SERVICE_ACCOUNT_PATH": "sensitive-path"})
    assert result.status == "FAIL"
    assert "sensitive" not in repr(result)


@pytest.mark.parametrize("raw", ["{invalid-private-material", "[]", "null", '{"type":"web-config","private_key":"do-not-echo"}'])
def test_malformed_credentials_do_not_leak_contents(raw):
    result = check_firebase_credentials({"FIREBASE_SERVICE_ACCOUNT_JSON": raw})
    assert result.status == "FAIL"
    assert "do-not-echo" not in repr(result) and "invalid-private-material" not in repr(result)


def test_relative_credential_path_and_invalid_signing_key(tmp_path):
    key_file = tmp_path / "account.json"
    key_file.write_text(json.dumps({
        "type": "service_account", "project_id": "unit-test", "client_email": "test@example.invalid",
        "private_key": "private-invalid-unit-test-key-do-not-echo", "token_uri": "https://oauth2.googleapis.com/token",
    }), encoding="utf-8")
    result = check_firebase_credentials({"FIREBASE_SERVICE_ACCOUNT_PATH": "account.json"}, tmp_path)
    assert result.status == "FAIL"
    assert "private-invalid-unit-test-key-do-not-echo" not in repr(result)


def test_missing_file_does_not_echo_its_path(tmp_path):
    result = check_firebase_credentials({"FIREBASE_SERVICE_ACCOUNT_PATH": "do-not-echo-path.json"}, tmp_path)
    assert result.status == "FAIL" and "do-not-echo-path" not in repr(result)


@pytest.mark.parametrize("storage", ["inline", "file"])
def test_valid_generated_signing_key_is_checked_without_external_calls(tmp_path, storage):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    raw = json.dumps({
        "type": "service_account", "project_id": "offline-unit-test",
        "client_email": "test@example.invalid", "private_key": pem,
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    if storage == "inline":
        values = {"FIREBASE_SERVICE_ACCOUNT_JSON": raw}
    else:
        (tmp_path / "account.json").write_text(raw, encoding="utf-8")
        values = {"FIREBASE_SERVICE_ACCOUNT_PATH": "account.json"}
    result = check_firebase_credentials(values, tmp_path)
    assert result.status == "PASS"
    assert pem not in repr(result) and "offline-unit-test" not in repr(result)


def test_exit_codes_distinguish_missing_settings_from_invalid_settings():
    assert exit_status([Check("one", "PASS", "ok")]) == 0
    assert exit_status([Check("key", "MISSING", "pending")]) == 2
    assert exit_status([Check("one", "MISSING", "pending"), Check("two", "FAIL", "invalid")]) == 1
