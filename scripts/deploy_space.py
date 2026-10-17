"""Create/update the Docker Space for the API, sync secrets, upload the build context, wait for /readyz.

Env: HF_TOKEN (write), plus any of the secrets listed in SECRETS (set on the Space when present).
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.errors import HfHubHTTPError

SPACE_ID = os.environ.get("SPACE_ID", "ashiksharon005/verdict-api")
SECRETS = ["HF_TOKEN", "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
           "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "TURNSTILE_SECRET_KEY"]
VARIABLES = {"ALLOWED_ORIGINS": os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,https://*.vercel.app")}
ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_S = int(os.environ.get("DEPLOY_TIMEOUT_S", "900"))


def stage(dest: Path) -> None:
    shutil.copytree(ROOT / "api" / "verdict_api", dest / "api" / "verdict_api",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "api" / "requirements.txt", dest / "api" / "requirements.txt")
    (dest / "training" / "verdict_train").mkdir(parents=True)
    for f in ("__init__.py", "checks.py", "scoring.py"):
        shutil.copy(ROOT / "training" / "verdict_train" / f, dest / "training" / "verdict_train" / f)
    shutil.copy(ROOT / "api" / "Dockerfile", dest / "Dockerfile")
    shutil.copy(ROOT / "api" / "SPACE_README.md", dest / "README.md")


def probe(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main() -> int:
    token = os.environ["HF_TOKEN"]
    api = HfApi(token=token)
    try:
        api.create_repo(SPACE_ID, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    except HfHubHTTPError as e:
        if e.response is not None and e.response.status_code == 402:
            msg = "Hugging Face requires a PRO subscription for Docker Spaces on free cpu-basic (HTTP 402)"
            print(f"::warning::{msg}")
            return 0 if os.environ.get("GITHUB_EVENT_NAME") == "push" else 1  # do not redden every push
        raise
    for name in SECRETS:
        if os.environ.get(name):
            api.add_space_secret(SPACE_ID, name, os.environ[name])
        else:
            print(f"skip secret {name} (not set)")
    for k, v in VARIABLES.items():
        api.add_space_variable(SPACE_ID, k, v)
    with tempfile.TemporaryDirectory() as tmp:
        stage(Path(tmp))
        info = api.upload_folder(folder_path=tmp, repo_id=SPACE_ID, repo_type="space",
                                 commit_message="Deploy API from GitHub Actions")
    print("uploaded:", info.commit_url)
    host = SPACE_ID.replace("/", "-").replace("_", "-").lower()
    url = f"https://{host}.hf.space"
    t0, last = time.time(), None
    while time.time() - t0 < TIMEOUT_S:
        stage_name = api.get_space_runtime(SPACE_ID).stage
        code = probe(url + "/readyz")
        if (stage_name, code) != last:
            print(f"[{int(time.time() - t0):4d}s] space={stage_name} readyz={code}", flush=True)
            last = (stage_name, code)
        if code == 200:
            print(f"healthy after {int(time.time() - t0)}s: {url}")
            return 0
        if stage_name in ("BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"):
            print("space failed:", stage_name, file=sys.stderr)
            return 1
        time.sleep(15)
    print("timed out waiting for /readyz", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
