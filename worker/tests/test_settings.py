from worker.app.core.settings import Settings


def test_worker_settings_do_not_read_api_env_file():
    env_files = Settings.model_config.get("env_file")

    assert env_files == ("worker/.env", ".env")
    assert "api/.env" not in env_files
