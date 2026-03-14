from pathlib import Path


def test_generated_app_has_repo_local_gitignore() -> None:
    content = Path("app/.gitignore").read_text(encoding="utf-8")

    assert "__pycache__/" in content
    assert ".venv/" in content
    assert "*.db" in content


def test_generated_app_has_compose_file_with_app_and_db_services() -> None:
    content = Path("app/docker-compose.yml").read_text(encoding="utf-8")

    assert "services:" in content
    assert "app:" in content
    assert "db:" in content
    assert "FLASK_APP: app:create_app" in content
    assert "DB_HOST: db" in content
