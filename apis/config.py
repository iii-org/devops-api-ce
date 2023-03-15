import json
import os
from pathlib import Path

FIXED = {
    # API versions
    "GITLAB_API_VERSION": "v4",
    "LOGGER_NAME": "devops.api",
    "DEBUG": False,
    "USE_RELOADER": False,
    "DOCUMENT_LEVEL": "public",
    "VERSION_CENTER_BASE_URL": "http://version-center.iiidevops.org",
    "ADMIN_GROUP": "sys-admin"
}

in_file = {}
JSON_FILE: Path = Path(__file__).parent.parent / "environments.json"
if os.path.isfile(JSON_FILE):
    with open(JSON_FILE, "r") as f:
        in_file = json.load(f)


def get(key):
    env = os.getenv(key)
    if env is not None:
        return env
    return in_file.get(key, FIXED.get(key, None))
