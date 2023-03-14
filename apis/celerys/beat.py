from api import celery
from resources.sync_redmine import init_data
from resources import logger


@celery.task()
def sync_redmine():
    logger.logger.info("run sync_redmine")
    init_data()
