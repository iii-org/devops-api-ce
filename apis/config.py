import json
import os
from pathlib import Path
import subprocess
from dotenv import load_dotenv
import urllib.parse

FIXED = {
    # API versions
    "GITLAB_API_VERSION": "v4",
    "LOGGER_NAME": "devops.api",
    "DEBUG": False,
    "USE_RELOADER": False,
    "DOCUMENT_LEVEL": "public",
    "VERSION_CENTER_BASE_URL": "http://version-center.iiidevops.org",
    "ADMIN_GROUP": "sys-admin",
}

# Define the base folder of the project
BASE_FOLDER: Path = Path(__file__).parent.parent

def handle_db_url():
    '''
    Encoding specific characters in the SQLALCHEMY_PASSWORD
    '''
    FIXED["SQLALCHEMY_DATABASE_URI"] = f'postgresql://{os.getenv("SQLALCHEMY_ACCOUNT")}:{urllib.parse.quote(os.getenv("SQLALCHEMY_PASSWORD"))}@{os.getenv("SQLALCHEMY_HOST")}/{os.getenv("SQLALCHEMY_DATABASE")}'

def get_current_branch():
    command = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()
    current_branch = output.decode().strip()
    return current_branch


def insert_env_file_in_env():
    env_files_folder = Path(__file__).parent.parent / "env"
    if os.path.exists(env_files_folder):
        current_branch = get_current_branch()
        env_files_folder = env_files_folder / f"{current_branch}.env"
        load_dotenv(env_files_folder)
        
        handle_db_url()
        

def get(key):
    return os.getenv(key) or FIXED.get(key)
