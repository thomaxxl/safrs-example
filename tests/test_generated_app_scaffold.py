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
    assert "dockerfile: Dockerfile" in content
    assert "CONFIG_MODULE: /workspace/app/config/base.py" in content
    assert "DB_HOST: db" in content


def test_generated_app_has_local_build_inputs() -> None:
    dockerfile = Path("app/Dockerfile").read_text(encoding="utf-8")
    requirements = Path("app/requirements.txt").read_text(encoding="utf-8")
    entrypoint = Path("app/entrypoint.sh").read_text(encoding="utf-8")
    config = Path("app/config/base.py").read_text(encoding="utf-8")
    init_sql = Path("app/docker/postgres-init/01-uuid-ossp.sql").read_text(encoding="utf-8")

    assert "COPY requirements.txt ." in dockerfile
    assert "CMD [\"./entrypoint.sh\"]" in dockerfile
    assert "safrs" in requirements
    assert "Flask-Migrate" in requirements
    assert "python -m app.bootstrap_db" in entrypoint
    assert "gunicorn" in entrypoint
    assert "SQLALCHEMY_DATABASE_URI" in config
    assert "uuid-ossp" in init_sql
