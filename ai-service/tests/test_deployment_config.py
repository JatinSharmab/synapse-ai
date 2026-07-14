from pydantic import SecretStr

from app.core.config import Settings


def test_render_supabase_bucket_environment_name_is_supported(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_BUCKET", "synapse-assets")

    settings = Settings(
        _env_file=None,
        app_env="test",
        ai_provider="mock",
        supabase_service_role_key=SecretStr("test-only-key"),
        supabase_url="https://project.example.test",
    )

    assert settings.supabase_storage_bucket == "synapse-assets"
