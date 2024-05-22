import os
import subprocess
import urllib.parse
from ast import literal_eval
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_configs: dict[str, Any] = {
    # API versions
    "GITLAB_API_VERSION": "v4",
    "RANCHER_API_VERSION": "v3",
    "LOGGER_NAME": "devops.api",
    "DEBUG": False,
    "USE_RELOADER": False,
    "DEFAULT_TRACE_ORDER": ["Epic", "Feature", "Test Plan"],
    "DOCUMENT_LEVEL": "public",
    "REDIS_BASE_URL": "devops-redis-service:6379",
    "VERSION_CENTER_BASE_URL": "https://version-center.iiidevops.org",
    "VERSION_CENTER_AGENT_BAES_URL": "version-center-agent:50052",
    "ADMIN_GROUP": "sys-admin",
}

# Define the base folder of the project
BASE_FOLDER: Path = Path(__file__).parent.parent

# Gitlab default variables
DEFAULT_REPO_GROUP = "iiidevops"
PIPELINE_REF_PJ = "iiidevops-templates/ci-template"
PIPELINE_REF_PJs = ["iiidevops-templates/ci-template", "iiidevops/temp-ci"]
TEST_PIPELINE_REF_PJs = ["iiidevops/ci-template", "iiidevops/test-temp-ci"]
CHECKMARX_AVAIL_VERSION = "v2.6.0"
VAR_SWITCH_AVAIL_VERSION = "v2.8.0"


class ValidateException(Exception):
    """
    The exception for the validation of the environment variables
    """

    pass


def _validate_env() -> None:
    """
    Implement the validation of the environment variables here.
    For example, if the environment variable is required, but not found, raise an exception.
    Or if the environment variable is not in the correct format, raise an exception.

    Returns:

    """
    pass


def _load() -> None:
    """
    Load the environment variables from the .env file or os environment variables.

    Returns:
        None
    """
    env_folder: Path = BASE_FOLDER / "env"
    if os.path.exists(env_folder):
        env_file: Path = env_folder / f"{_get_branch_name()}.env"

        if os.path.isfile(env_file):
            load_dotenv(env_file)

        # For CE version, force need to load the env file
        else:
            raise RuntimeError(f"Cannot find the env file: {env_file}")

    sql: str = (
        f"postgresql://"
        f'{get("SQLALCHEMY_ACCOUNT")}:'
        f'{urllib.parse.quote_plus(get("SQLALCHEMY_PASSWORD", ""))}@'
        f'{get("SQLALCHEMY_HOST")}/'
        f'{get("SQLALCHEMY_DATABASE")}'
    )

    _configs["SQLALCHEMY_DATABASE_URI"] = sql

    _validate_env()


def _get_branch_name() -> str:
    """
    Get the current branch name, if not found, return "default".

    Returns:
        str: The current branch name
    """
    command: list[str] = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
    process: subprocess.Popen = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()
    branch_name: str = output.decode().strip()

    if not branch_name:
        branch_name = "HEAD"

    return branch_name


def _convert_bool(value: str) -> bool:
    """
    Convert the string value to boolean value

    Args:
        value: The string value

    Returns:
        bool: The boolean value
    """
    if value.lower() in ["true", "t", "1", "yes", "y", "on"]:
        return True

    elif value.lower() in ["false", "f", "0", "no", "n", "off"]:
        return False

    else:
        raise ValueError(f"Cannot convert {value} to boolean value.")


def get(key: str, default: Any = None, convert: bool = False) -> Any:
    """
    Get the value of the key from the config file, if not found, return the default value

    Args:
        key: The key of the config
        default: The default value if the key is not found
        convert: If the value should be converted to the correct type, otherwise, return the string type value

    Returns:
        Any: The value of the key
    """
    env: Any = os.getenv(key)

    if env is not None and convert:
        if isinstance(env, str):
            try:
                env = _convert_bool(env)

            except ValueError:
                try:
                    # Auto guess type, only support int, float, list, dict
                    env = literal_eval(env)

                except (ValueError, SyntaxError):
                    pass
        else:
            raise ValueError(f"Cannot convert {env}, should be a string.")

    if env is not None:
        return env

    if key in _configs and _configs[key] is not None:
        return _configs[key]

    else:
        return default


# Indirectly call the _load function
_load()

DEBUG: bool = get("DEBUG", False, convert=True)
