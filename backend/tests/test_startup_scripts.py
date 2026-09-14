import os
import subprocess
import tempfile
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
START_SH_PATH = os.path.join(ROOT_DIR, "start.sh")

def run_start_sh(env_overrides=None, args=None, cwd=None):
    """Executes start.sh with dry-run flag and custom environment variables."""
    cmd = ["bash", START_SH_PATH, "--dry-run"]
    if args:
        cmd.extend(args)

    base_env = os.environ.copy()
    # Clean out any ambient secret manager variables for test isolation
    for k in ["DOPPLER_ENVIRONMENT", "DOPPLER_CONFIG", "INFISICAL_PROJECT_ID", "INFISICAL_ENV", "INFISICAL_INJECTED", "INFISICAL_TOKEN"]:
        base_env.pop(k, None)

    if env_overrides:
        base_env.update(env_overrides)

    result = subprocess.run(
        cmd,
        cwd=cwd or ROOT_DIR,
        env=base_env,
        capture_output=True,
        text=True,
        timeout=10
    )
    return result

def test_start_sh_doppler_env_active():
    """Verify that active Doppler environment variable is detected."""
    res = run_start_sh(env_overrides={"DOPPLER_ENVIRONMENT": "staging", "DOPPLER_CONFIG": "stg"})
    assert res.returncode == 0
    assert "Secrets injected via Doppler (Config: stg / Env: staging)" in res.stdout
    assert "[Dry-Run] Secret management resolved successfully" in res.stdout

def test_start_sh_infisical_env_active():
    """Verify that active INFISICAL_ENV variable is detected."""
    res = run_start_sh(env_overrides={"INFISICAL_ENV": "production"})
    assert res.returncode == 0
    assert "Secrets injected via Infisical" in res.stdout
    assert "[Dry-Run] Secret management resolved successfully" in res.stdout

def test_start_sh_infisical_project_id_active():
    """Verify that active INFISICAL_PROJECT_ID variable is detected."""
    res = run_start_sh(env_overrides={"INFISICAL_PROJECT_ID": "proj_12345"})
    assert res.returncode == 0
    assert "Secrets injected via Infisical" in res.stdout
    assert "[Dry-Run] Secret management resolved successfully" in res.stdout

def test_start_sh_infisical_injected_flag():
    """Verify that INFISICAL_INJECTED=1 prevents infinite execution loop."""
    res = run_start_sh(env_overrides={"INFISICAL_INJECTED": "1"})
    assert res.returncode == 0
    assert "Secrets injected via Infisical" in res.stdout
    assert "[Dry-Run] Secret management resolved successfully" in res.stdout

def test_start_sh_local_env_file():
    """Verify that local backend/.env is used when no secret manager is active in env."""
    with tempfile.TemporaryDirectory() as temp_dir:
        proj_dir = os.path.join(temp_dir, "project")
        os.makedirs(os.path.join(proj_dir, "backend"), exist_ok=True)
        with open(os.path.join(proj_dir, "backend", ".env"), "w") as f:
            f.write("LLM_MODEL=test-model\n")

        sh_path = os.path.join(proj_dir, "start.sh")
        with open(START_SH_PATH, "r") as src, open(sh_path, "w") as dst:
            dst.write(src.read())
        os.chmod(sh_path, 0o755)

        env = os.environ.copy()
        for k in ["DOPPLER_ENVIRONMENT", "DOPPLER_CONFIG", "INFISICAL_PROJECT_ID", "INFISICAL_ENV", "INFISICAL_INJECTED", "INFISICAL_TOKEN"]:
            env.pop(k, None)

        res = subprocess.run(
            ["bash", sh_path, "--dry-run"],
            cwd=proj_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )
        assert res.returncode == 0
        assert "Secrets loaded from local backend/.env" in res.stdout
        assert "[Dry-Run] Secret management resolved successfully" in res.stdout

def test_start_sh_infisical_auto_launch_simulation():
    """Verify that Infisical auto-launch triggers when .infisical.json is present and infisical CLI exists."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock bin directory with a dummy infisical executable
        mock_bin = os.path.join(temp_dir, "bin")
        os.makedirs(mock_bin, exist_ok=True)
        mock_infisical = os.path.join(mock_bin, "infisical")
        # When called as `infisical run -- bash start.sh --dry-run`, echo mock run and execute command
        with open(mock_infisical, "w") as f:
            f.write("#!/bin/bash\nif [ \"$1\" = \"run\" ]; then shift 2; exec \"$@\"; fi\n")
        os.chmod(mock_infisical, 0o755)

        # Create dummy project folder without backend/.env but with .infisical.json
        proj_dir = os.path.join(temp_dir, "project")
        os.makedirs(proj_dir, exist_ok=True)
        with open(os.path.join(proj_dir, ".infisical.json"), "w") as f:
            f.write('{"workspaceId": "ws_123"}')

        # Copy start.sh to test project
        sh_path = os.path.join(proj_dir, "start.sh")
        with open(START_SH_PATH, "r") as src, open(sh_path, "w") as dst:
            dst.write(src.read())
        os.chmod(sh_path, 0o755)

        env = os.environ.copy()
        for k in ["DOPPLER_ENVIRONMENT", "DOPPLER_CONFIG", "INFISICAL_PROJECT_ID", "INFISICAL_ENV", "INFISICAL_INJECTED", "INFISICAL_TOKEN"]:
            env.pop(k, None)
        env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"

        res = subprocess.run(
            ["bash", sh_path, "--dry-run"],
            cwd=proj_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )
        assert res.returncode == 0
        assert "Launching application with Infisical secret injection..." in res.stdout
        assert "Secrets injected via Infisical" in res.stdout

def test_start_sh_fallback_notice_when_no_env_or_manager():
    """Verify helpful notice message is printed when no backend/.env and no secret manager configured."""
    with tempfile.TemporaryDirectory() as temp_dir:
        proj_dir = os.path.join(temp_dir, "project")
        os.makedirs(proj_dir, exist_ok=True)

        sh_path = os.path.join(proj_dir, "start.sh")
        with open(START_SH_PATH, "r") as src, open(sh_path, "w") as dst:
            dst.write(src.read())
        os.chmod(sh_path, 0o755)

        env = os.environ.copy()
        for k in ["DOPPLER_ENVIRONMENT", "DOPPLER_CONFIG", "INFISICAL_PROJECT_ID", "INFISICAL_ENV", "INFISICAL_INJECTED", "INFISICAL_TOKEN"]:
            env.pop(k, None)
        # Empty PATH so neither doppler nor infisical is found
        env["PATH"] = "/usr/bin:/bin"

        res = subprocess.run(
            ["bash", sh_path, "--dry-run"],
            cwd=proj_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )
        assert res.returncode == 0
        assert "backend/.env not found and no Secret Manager active" in res.stdout
        assert "Doppler:   doppler run -- ./start.sh" in res.stdout
        assert "Infisical: infisical run -- ./start.sh" in res.stdout
