import io
import logging
import os
import config
import model
from model import db, UIRouteData, PluginSoftware, SystemParameter
from resources.logger import logger
from migrate.upgrade_function.ui_route_upgrade import ui_route_first_version
from migrate.upgrade_function import v1_22_upgrade
from resources.router import update_plugin_hidden
from resources.system import system_git_commit_id

from pathlib import Path
from resources.logger import logger
from alembic.command import current, upgrade
from alembic.config import Config
from alembic.script import ScriptDirectory


_config_file: Path = config.BASE_FOLDER / "alembic.ini"
_script_location: Path = config.BASE_FOLDER / "apis" / "alembic"

_alembic_config: Path = config.BASE_FOLDER / "alembic.ini"
_alembic_config_template: Path = config.BASE_FOLDER / "_alembic.ini"

_buffer: io.StringIO = io.StringIO()
_logger: logging.Logger = logging.getLogger("alembic.runtime.migration")

# Rebuild init file since ini is not git tracked or in debug mode
if not os.path.isfile(_alembic_config) or config.get("DEBUG"):
    with open(_alembic_config, "w") as ini:
        with open(_alembic_config_template, "r") as template:
            for line in template:
                if line.startswith("sqlalchemy.url"):
                    ini.write(f"sqlalchemy.url = {config.get('SQLALCHEMY_DATABASE_URI').replace('%', '%%')}\n")
                else:
                    ini.write(line)


# Each time you add a migration, add a version code here.

VERSIONS = ["0.0.0.0", "0.0.1.0", "0.0.1.1"]


def _upgrade(version):
    """
    Upgraded function need to check it can handle multi calls situation,
    just in case multi pods will call it several times.
    ex. Insert data need to check data has already existed or not.
    """
    pass


def recreate_ui_route():
    UIRouteData.query.delete()
    ui_route_first_version()

    for plugin_software in PluginSoftware.query.all():
        update_plugin_hidden(plugin_software.name, plugin_software.disabled)


def init():
    latest_api_version, deploy_version = VERSIONS[-1], config.get("DEPLOY_VERSION")
    if deploy_version is None:
        deploy_version = system_git_commit_id().get("git_tag")

    logger.info(f"Create NexusVersion, api_version={latest_api_version}, deploy_version={deploy_version}")
    new = model.NexusVersion(api_version=latest_api_version, deploy_version=deploy_version)
    db.session.add(new)
    db.session.commit()

    # For the new server, need to add some default value
    # 1.22
    logger.info("Start insert default value in v1.22")
    v1_22_upgrade.insert_default_value_in_lock()
    logger.info("Insert default value in Lock done")
    v1_22_upgrade.insert_default_value_in_system_parameter()
    logger.info("Insert default value in SystemParameter done")
    v1_22_upgrade.insert_default_value_in_default_alert_days()
    logger.info("Insert default value in DefaultAlertDays done")
    ui_route_first_version()
    logger.info("Insert default value in UiRouteData done")


def needs_upgrade(current, target):
    r = current.split(".")
    c = target.split(".")
    for i in range(4):
        if int(c[i]) > int(r[i]):
            return True
        elif int(c[i]) < int(r[i]):
            return False
    return False


def alembic_get_config(to_stringio: bool = False) -> Config:
    """
    Get alembic config

    Args:
        to_stringio: If True, return config from stdout to StringIO

    Returns:
        Config: Alembic config
    """
    # Reset before use
    _buffer.seek(0)

    if not to_stringio:
        _config: Config = Config(f"{_config_file}")

    else:
        _config: Config = Config(f"{_config_file}", stdout=_buffer)

    _config.set_main_option("script_location", f"{_script_location}")

    return _config


def alembic_upgrade(version: str = "head") -> None:
    """
    Upgrade alembic

    Args:
        version: revision to upgrade

    Returns:
        None
    """
    upgrade(alembic_get_config(), version)


def alembic_need_upgrade() -> bool:
    """
    Check if alembic need upgrade

    Returns:
        bool: True if alembic need upgrade
    """
    if alembic_get_current() == alembic_get_head():
        return False
    return True


def alembic_get_current() -> str:
    """
    Get current alembic revision

    Returns:
        str: Current alembic revision
    """
    # https://stackoverflow.com/a/61770854
    _logger.disabled = True

    current(alembic_get_config(True))
    _out: str = _buffer.getvalue().strip()

    _logger.disabled = False
    return _out[:12]


def alembic_get_head() -> str:
    """
    Get alembic head revision

    Returns:
        str: Alembic head revision
    """
    _script: ScriptDirectory = ScriptDirectory.from_config(alembic_get_config())

    return _script.get_current_head()


def current_version():
    if db.engine.has_table(model.NexusVersion.__table__.name):
        # Cannot write in ORM here since NexusVersion table itself may be modified
        result = db.engine.execute("SELECT api_version FROM nexus_version")
        row = result.fetchone()
        result.close()
        if row is not None:
            current = row["api_version"]
        else:
            # This is a new server, so NexusVersion table scheme should match the ORM
            current = "0.0.0.0"
            new = model.NexusVersion(api_version=current)
            db.session.add(new)
            db.session.commit()
    else:
        # Backward compatibility
        if os.path.exists(".api_version"):
            with open(".api_version", "r") as f:
                current = f.read()
        else:
            current = "0.0.0.0"
    return current


def run():
    current = current_version()
    try:
        for version in VERSIONS:
            if needs_upgrade(current, version):
                current, deploy_version = version, config.get("DEPLOY_VERSION")
                row = model.NexusVersion.query.first()
                if row.deploy_version != deploy_version:
                    row.deploy_version = deploy_version
                row.api_version = current
                db.session.commit()
                logger.info("Upgrade to {0}".format(version))
                if alembic_need_upgrade():
                    alembic_upgrade()
                _upgrade(version)
    except Exception as e:
        logger.exception(str(e))
        raise e
