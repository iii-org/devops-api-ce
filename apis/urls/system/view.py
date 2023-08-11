import util
from flask_apispec import doc, marshal_with, use_kwargs
from flask_apispec.views import MethodResource
from flask_restful import Resource
from resources.system import (
    send_merge_request_notification,
    system_git_commit_id,
)
from resources.devops_version import VersionCenter

class SystemInfoReport(Resource):
    def put(self):
        VersionCenter().update_iii_host_info_in_vc()
        return util.success()


# noinspection PyMethodMayBeStatic
class SystemGitCommitID(Resource):
    def get(self):
        return util.success(system_git_commit_id())


@doc(
    tags=["Merge Request"],
    description="Check system all merge request and send notification message to user",
)
class SendMergeRequestNotification(MethodResource):
    def get(self):
        send_merge_request_notification()
        return util.success()
