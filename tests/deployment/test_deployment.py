"""Deployment hygiene tests — Phase 14.

Validates:
  - Dockerfiles are non-root and have HEALTHCHECK (§15 CLAUDE.md)
  - docker-compose.yml has the four required services with healthchecks
  - .env.example covers every variable in CLAUDE.md §10.1
  - No .env file is committed to the repository
  - Terraform roots have main.tf, variables.tf, and outputs.tf
  - Deployment scripts exist and are executable on POSIX
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Dockerfile hygiene
# ---------------------------------------------------------------------------


class TestDockerfiles:
    def _read(self, path: Path) -> str:
        assert path.exists(), f"Dockerfile not found: {path}"
        return path.read_text(encoding="utf-8")

    def test_backend_dockerfile_exists(self) -> None:
        assert (REPO_ROOT / "backend" / "Dockerfile").exists()

    def test_frontend_dockerfile_exists(self) -> None:
        assert (REPO_ROOT / "frontend" / "Dockerfile").exists()

    def test_backend_dockerfile_has_healthcheck(self) -> None:
        content = self._read(REPO_ROOT / "backend" / "Dockerfile")
        assert "HEALTHCHECK" in content, "backend Dockerfile must have HEALTHCHECK"

    def test_frontend_dockerfile_has_healthcheck(self) -> None:
        content = self._read(REPO_ROOT / "frontend" / "Dockerfile")
        assert "HEALTHCHECK" in content, "frontend Dockerfile must have HEALTHCHECK"

    def test_backend_dockerfile_non_root(self) -> None:
        content = self._read(REPO_ROOT / "backend" / "Dockerfile")
        assert "USER app" in content or "USER 1001" in content, (
            "backend Dockerfile must run as non-root user"
        )

    def test_frontend_dockerfile_non_root(self) -> None:
        content = self._read(REPO_ROOT / "frontend" / "Dockerfile")
        assert "USER app" in content or "USER 1001" in content, (
            "frontend Dockerfile must run as non-root user"
        )

    def test_backend_dockerfile_multistage(self) -> None:
        content = self._read(REPO_ROOT / "backend" / "Dockerfile")
        assert content.count("FROM ") >= 2, (
            "backend Dockerfile should use multi-stage build"
        )

    def test_frontend_dockerfile_standalone_output(self) -> None:
        # The next.config.ts must have output: "standalone"
        config = REPO_ROOT / "frontend" / "next.config.ts"
        assert config.exists()
        assert "standalone" in config.read_text(encoding="utf-8"), (
            "next.config.ts must set output: 'standalone'"
        )


# ---------------------------------------------------------------------------
# docker-compose.yml
# ---------------------------------------------------------------------------


class TestDockerCompose:
    def _content(self) -> str:
        path = REPO_ROOT / "docker-compose.yml"
        assert path.exists(), "docker-compose.yml not found"
        return path.read_text(encoding="utf-8")

    def test_compose_has_backend_service(self) -> None:
        assert "backend:" in self._content()

    def test_compose_has_frontend_service(self) -> None:
        assert "frontend:" in self._content()

    def test_compose_has_redis_service(self) -> None:
        assert "redis:" in self._content()

    def test_compose_has_qdrant_service(self) -> None:
        assert "qdrant:" in self._content()

    def test_compose_services_have_healthchecks(self) -> None:
        content = self._content()
        # Each service should have a healthcheck
        assert content.count("healthcheck:") >= 4, (
            "All 4 services must have healthcheck definitions"
        )

    def test_compose_uses_named_volumes(self) -> None:
        content = self._content()
        assert "volumes:" in content, "docker-compose.yml must define named volumes"

    def test_compose_has_restart_policy(self) -> None:
        content = self._content()
        assert "unless-stopped" in content, (
            "Services must have restart: unless-stopped"
        )

    def test_compose_depends_on_backend(self) -> None:
        content = self._content()
        # Frontend must depend on backend
        assert "depends_on:" in content


# ---------------------------------------------------------------------------
# .env.example coverage — every CLAUDE.md §10.1 variable must be listed
# ---------------------------------------------------------------------------

_REQUIRED_ENV_VARS = [
    "DEMO_MODE",
    "ENVIRONMENT",
    "CORS_ORIGINS",
    "JWT_SECRET",
    "SUPABASE_JWT_SECRET",
    "DATABASE_URL",
    "CHECKPOINT_DB_PATH",
    "REDIS_URL",
    "USE_FAKE_REDIS",
    "LLM_PROVIDER",
    "LLM_API_KEY",
    "LLM_MODEL",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "VECTOR_STORE",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION",
    "APPROVAL_REQUIRED_FOR_REFUNDS",
    "MAX_REFUND_WITHOUT_APPROVAL",
    "TOOL_TIMEOUT_SECONDS",
    "RATE_LIMIT_PER_MINUTE",
    "SAMPLE_DATA_DIR",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_PROJECT",
]


class TestEnvExample:
    def _content(self) -> str:
        path = REPO_ROOT / ".env.example"
        assert path.exists(), ".env.example not found"
        return path.read_text(encoding="utf-8")

    def test_env_example_exists(self) -> None:
        assert (REPO_ROOT / ".env.example").exists()

    @pytest.mark.parametrize("var_name", _REQUIRED_ENV_VARS)
    def test_env_example_contains_var(self, var_name: str) -> None:
        content = self._content()
        assert var_name in content, (
            f".env.example is missing variable: {var_name}"
        )

    def test_env_example_has_no_real_secrets(self) -> None:
        content = self._content()
        # API keys and JWT secrets must be blank placeholders
        lines_with_key = [
            line for line in content.splitlines()
            if "API_KEY=" in line or "JWT_SECRET=" in line
        ]
        for line in lines_with_key:
            value = line.split("=", 1)[-1].strip()
            assert value in ("", '""', "''"), (
                f".env.example must not contain real secrets: {line!r}"
            )


# ---------------------------------------------------------------------------
# No .env committed — §18.1 rule 11
# ---------------------------------------------------------------------------


class TestNoCommittedDotEnv:
    def test_dot_env_not_in_repo_root(self) -> None:
        env_path = REPO_ROOT / ".env"
        # .env may exist on disk (developer local), but it must be in .gitignore
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8") if (REPO_ROOT / ".gitignore").exists() else ""
        if env_path.exists():
            assert ".env" in gitignore, (
                ".env exists but is not listed in .gitignore — it must not be committed"
            )

    def test_gitignore_excludes_env_files(self) -> None:
        gitignore_path = REPO_ROOT / ".gitignore"
        assert gitignore_path.exists(), ".gitignore must exist"
        content = gitignore_path.read_text(encoding="utf-8")
        assert ".env" in content, ".gitignore must exclude .env files"

    def test_gitignore_excludes_data_directory(self) -> None:
        gitignore_path = REPO_ROOT / ".gitignore"
        content = gitignore_path.read_text(encoding="utf-8")
        assert "data/" in content or "/data/" in content, (
            ".gitignore must exclude data/ directory (contains SQLite DBs)"
        )

    def test_gitignore_excludes_tfvars_local(self) -> None:
        gitignore_path = REPO_ROOT / ".gitignore"
        content = gitignore_path.read_text(encoding="utf-8")
        assert "terraform.tfvars" in content or "*.tfvars" in content, (
            ".gitignore must exclude terraform.tfvars (may contain secrets)"
        )


# ---------------------------------------------------------------------------
# Terraform structure
# ---------------------------------------------------------------------------


class TestTerraformStructure:
    @pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
    def test_terraform_root_has_main_tf(self, cloud: str) -> None:
        path = REPO_ROOT / "deployment" / cloud / "main.tf"
        assert path.exists(), f"deployment/{cloud}/main.tf not found"

    @pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
    def test_terraform_root_has_variables_tf(self, cloud: str) -> None:
        path = REPO_ROOT / "deployment" / cloud / "variables.tf"
        assert path.exists(), f"deployment/{cloud}/variables.tf not found"

    @pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
    def test_terraform_root_has_outputs_tf(self, cloud: str) -> None:
        path = REPO_ROOT / "deployment" / cloud / "outputs.tf"
        assert path.exists(), f"deployment/{cloud}/outputs.tf not found"

    @pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
    def test_terraform_has_env_var_files(self, cloud: str) -> None:
        for env in ["dev", "staging", "prod"]:
            path = REPO_ROOT / "deployment" / cloud / "environments" / env / "terraform.tfvars"
            assert path.exists(), (
                f"deployment/{cloud}/environments/{env}/terraform.tfvars not found"
            )

    def test_terraform_modules_exist(self) -> None:
        modules = [
            "networking", "container-registry", "secrets",
            "redis", "compute", "load-balancer", "monitoring",
        ]
        for module in modules:
            path = REPO_ROOT / "deployment" / "modules" / module / "main.tf"
            assert path.exists(), f"Terraform module missing: modules/{module}/main.tf"

    @pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
    def test_variables_tf_has_image_tag(self, cloud: str) -> None:
        path = REPO_ROOT / "deployment" / cloud / "variables.tf"
        content = path.read_text(encoding="utf-8")
        assert "image_tag" in content, (
            f"deployment/{cloud}/variables.tf must define image_tag variable"
        )

    @pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
    def test_variables_tf_has_environment_validation(self, cloud: str) -> None:
        path = REPO_ROOT / "deployment" / cloud / "variables.tf"
        content = path.read_text(encoding="utf-8")
        assert "dev" in content and "staging" in content and "prod" in content, (
            f"deployment/{cloud}/variables.tf must validate environment values"
        )


# ---------------------------------------------------------------------------
# CI workflows
# ---------------------------------------------------------------------------


class TestCIWorkflows:
    @pytest.mark.parametrize("workflow", [
        "test.yml",
        "security.yml",
        "docker-build.yml",
        "terraform-validate.yml",
        "_deploy.yml",
    ])
    def test_workflow_file_exists(self, workflow: str) -> None:
        path = REPO_ROOT / ".github" / "workflows" / workflow
        assert path.exists(), f".github/workflows/{workflow} not found"

    def test_test_workflow_runs_pytest(self) -> None:
        content = (REPO_ROOT / ".github" / "workflows" / "test.yml").read_text()
        assert "pytest" in content

    def test_test_workflow_runs_frontend_tests(self) -> None:
        content = (REPO_ROOT / ".github" / "workflows" / "test.yml").read_text()
        assert "npm run test" in content or "npm test" in content

    def test_deploy_workflow_uses_environment_protection(self) -> None:
        content = (REPO_ROOT / ".github" / "workflows" / "_deploy.yml").read_text()
        assert "prod-apply" in content, (
            "_deploy.yml must reference prod-apply environment for production deploys"
        )

    def test_security_workflow_has_secret_scan(self) -> None:
        content = (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text()
        assert "gitleaks" in content.lower() or "secret" in content.lower()


# ---------------------------------------------------------------------------
# Deployment scripts
# ---------------------------------------------------------------------------


class TestDeploymentScripts:
    @pytest.mark.parametrize("script", [
        "build_and_push.sh",
        "deploy.sh",
        "smoke_test.sh",
        "rollback.sh",
        "destroy.sh",
    ])
    def test_script_exists(self, script: str) -> None:
        path = REPO_ROOT / "deployment" / "scripts" / script
        assert path.exists(), f"deployment/scripts/{script} not found"

    def test_deploy_script_refuses_auto_approve_for_prod(self) -> None:
        content = (REPO_ROOT / "deployment" / "scripts" / "deploy.sh").read_text()
        assert "auto-approve" in content.lower() and "prod" in content.lower(), (
            "deploy.sh must refuse --auto-approve for staging/prod"
        )

    def test_destroy_script_refuses_auto_approve_for_prod(self) -> None:
        content = (REPO_ROOT / "deployment" / "scripts" / "destroy.sh").read_text()
        assert "auto-approve" in content.lower() and "prod" in content.lower()
