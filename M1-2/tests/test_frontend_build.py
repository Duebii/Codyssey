import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("frontend_build", Path(__file__).parents[1] / "scripts" / "build_frontend.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("url", ["https://example.com/", "http://127.0.0.1:8000", "http://localhost:8000"])
def test_public_api_url(url):
    assert module.validate_api_url(url) == url.rstrip("/")


@pytest.mark.parametrize("url", ["https://user:secret@example.com", "https://example.com?key=x", "http://example.com", "javascript:alert(1)", "https://example.com/#x", 'https://example.com/\";alert(1)'])
def test_no_unsafe_or_secret_configuration(url):
    with pytest.raises(ValueError):
        module.validate_api_url(url)


def test_production_never_builds_with_a_local_or_missing_backend(monkeypatch):
    monkeypatch.delenv('API_BASE_URL', raising=False)
    with pytest.raises(ValueError, match='API_BASE_URL'):
        module.build(production=True)
    with pytest.raises(ValueError):
        module.validate_api_url('http://127.0.0.1:8000', production=True)
    with pytest.raises(ValueError):
        module.validate_api_url('https://backend.example.com/api', production=True)


def test_release_only_copies_allowlisted_assets_and_public_url(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setenv('API_BASE_URL', 'https://backend.example.com')
    monkeypatch.setenv('OPENAI_API_KEY', 'PRIVATE-DO-NOT-PUBLISH')
    source = tmp_path / 'frontend'
    source.mkdir()
    for name in module.ASSETS:
        (source / name).write_text('public asset', encoding='utf-8')
    (source / '.env').write_text('PRIVATE-DO-NOT-PUBLISH', encoding='utf-8')
    module.build(production=True)
    output = tmp_path / 'dist'
    assert {path.name for path in output.iterdir()} == {*module.ASSETS, 'config.js'}
    assert all('PRIVATE-DO-NOT-PUBLISH' not in path.read_text(encoding='utf-8') for path in output.iterdir())
    assert 'https://backend.example.com' in (output / 'config.js').read_text(encoding='utf-8')
    # A previous accidental file must not silently ship with the next build.
    (output / 'credentials.json').write_text('PRIVATE-DO-NOT-PUBLISH', encoding='utf-8')
    with pytest.raises(ValueError, match='dist'):
        module.build(production=True)
