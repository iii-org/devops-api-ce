import uuid
import model
from resources import role, apiError
from resources.apiError import DevOpsError
import config
import model
import util
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from requests import Response
from resources.system import system_git_commit_id
from resources.logger import logger
from datetime import datetime


class VersionCenter:
    def __init__(self):
        """
        Login to get token every time is in case of token expired.
        """

        self.__get_iii_verions_info()
        self.__login()

    def __get_iii_verions_info(self) -> None:
        nexus_version = model.NexusVersion.query.one()
        self.dp_uuid, self.dp_version = nexus_version.deployment_uuid, nexus_version.deploy_version

    def __login(self) -> None:
        """
        Login will also create a deployment(if not exist) or update the deploymeny info in version center.
        """

        response: Response = self.post(
            "/login",
            params={
                "uuid": self.dp_uuid,
                "name": config.get("DEPLOYMENT_NAME") or config.get("DEPLOYER_NODE_IP"),
                "type": "lite",
            },
            with_token=False,
        )

        self.center_token = response.json().get("data", {}).get("access_token", None)

    def update_version_in_db_and_vc(self) -> Response:
        """
        Record current deployment to version center and iii DB.

        Returns:
            None
        """
        logger.info(f"Current deploy_version: {self.dp_version}, deployment_uuid: {self.dp_uuid}.")

        _version = system_git_commit_id().get("git_tag")
        if self.dp_version != _version:
            model.NexusVersion.query.filter_by(deployment_uuid=self.dp_uuid).update({"deploy_version": _version})
            model.db.session.commit()
            self.dp_version = _version
            logger.info(f"Update deploy_version to {_version}.")

        return self.post("/report_update", data={"version_name": _version, "uuid": self.dp_uuid})

    def update_iii_host_info_in_vc(self) -> Response:
        """
        Update iii host info to version center.
        """
        
        ret = {
            "update_at": str(datetime.now()),
            "iiidevops": {
                "deploy_version": self.dp_version,
                "deployment_uuid": self.dp_uuid,
            },
        }
        return self.post("/report_info", data={"iiidevops": ret, "uuid": self.dp_uuid})

    def _call_api(
        self,
        path: str,
        method: str,
        *,
        headers: dict = None,
        params: dict = None,
        data: dict = None,
        with_token: bool = True,
        retry: bool = False,
    ) -> Response:
        """
        Call version center API.

        Args:
            path: The path of API, e.g. /__login
            method: The method of API, only support GET and POST.
            headers: The headers of API.
            params: The params of API.
            data: The data of API.
            with_token: If True, add token to headers.
            retry: If True, retry once when token expire.

        Returns:
            Response: The response of API.
        """
        if headers is None:
            headers = dict()

        if params is None:
            params = dict()

        if with_token:
            headers["Authorization"] = f"Bearer {self.center_token}"

        if path.startswith("/"):
            path = path[1:]

        if method not in ["GET", "POST"]:
            raise DevOpsError(500, "Only GET and POST method are supported.")

        url: str = f"{config.get('VERSION_CENTER_BASE_URL')}/{path}"
        output: Response = util.api_request(method, url, headers, params, data)

        # When token expire
        if output.status_code == 401 and not retry:
            self.__login()
            return self._call_api(method, path, headers=headers, params=params, data=data, with_token=True, retry=True)

        if int(output.status_code / 100) != 2:
            raise DevOpsError(
                output.status_code,
                "Got non-2xx response from Version center.",
                error=apiError.error_3rd_party_api("Version Center", output),
            )
        return output

    def get(
        self,
        path: str,
        *,
        headers: dict = None,
        params: dict = None,
        data: dict = None,
        with_token: bool = True,
        retry: bool = False,
    ) -> Response:
        """
        Call version center GET API.

        Args:
            path: The path of API, e.g. /login
            headers: The headers of API.
            params: The params of API.
            data: The data of API.
            with_token: If True, add token to headers.
            retry: If True, retry once when token expire.

        Returns:
            Response: The response of API.
        """
        return self._call_api(
            path, "GET", headers=headers, params=params, data=data, with_token=with_token, retry=retry
        )

    def post(
        self,
        path: str,
        *,
        headers: dict = None,
        params: dict = None,
        data: dict = None,
        with_token: bool = True,
        retry: bool = False,
    ) -> Response:
        """
        Call version center POST API.

        Args:
            path: The path of API, e.g. /login
            headers: The headers of API.
            params: The params of API.
            data: The data of API.
            with_token: If True, add token to headers.
            retry: If True, retry once when token expire.

        Returns:
            Response: The response of API.
        """
        return self._call_api(
            path, "POST", headers=headers, params=params, data=data, with_token=with_token, retry=retry
        )


def set_deployment_uuid():
    my_uuid = uuid.uuid1()
    row = model.NexusVersion.query.first()
    row.deployment_uuid = my_uuid
    model.db.session.commit()
    return my_uuid



def current_devops_version():
    return model.NexusVersion.query.one().deploy_version


def get_deployment_info():
    row = model.NexusVersion.query.one()
    return {
        "version_name": row.deploy_version,
        "deployment_name": config.get("DEPLOYER_NODE_IP"),
        "deployment_uuid": row.deployment_uuid,
    }


# ------------------ Resources ------------------
class DevOpsVersion(Resource):
    @jwt_required()
    def get(self):
        return util.success(get_deployment_info())


# class DevOpsVersionCheck(Resource):
#     @jwt_required()
#     def get(self):
#         role.require_admin()
#         return util.success(has_devops_update())


# class DevOpsVersionUpdate(Resource):
#     @jwt_required()
#     def patch(self):
#         role.require_admin()
#         versions = has_devops_update()["latest_version"]
#         update_deployment(versions)
#         return util.success(versions)
