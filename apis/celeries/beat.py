from api import celery
from resources.sync_redmine import init_data
from resources import project, project_relation
from resources import logger


def error_handler(func):
    def wrap(*args, **kwargs):
        logger.logger.info(f"Run {func.__name__}")
        try:
            ret = func(*args, **kwargs)
            logger.logger.info(f"Run {func.__name__} successfully.")
            return ret
        except Exception as e:
            logger.logger.exception(str(e))
            logger.logger.info(f"Run {func.__name__} unsuccessfully.")

    return wrap


@celery.task(name="sync_redmine")
@error_handler
def sync_redmine() -> None:
    init_data()


@celery.task(name="sync_project_issue_calculation")
@error_handler
def sync_project_issue_calculation() -> None:
    project.sync_project_issue_calculate()


@celery.task(name="sync_project_relation")
@error_handler
def sync_project_relation() -> None:
    project_relation.sync_project_relation()
