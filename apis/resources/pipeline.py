import base64
import json
from sqlalchemy.sql.operators import exists

import werkzeug
import yaml
from flask_jwt_extended import jwt_required
from flask_restful import Resource, reqparse
from flask import send_file

import resources.apiError as apiError
import util as util
import time
import websocket
from flask_socketio import emit, disconnect, Namespace
from model import db  #  remove ProjectPluginRelation ,PipelineLogsCache, Project
from nexus import nx_get_project_plugin_relation
from resources import role
from .gitlab import GitLab
from typing import Union, Any

# from .rancher import rancher
from os import listdir, makedirs
from shutil import rmtree

gitlab = GitLab()


def pipeline_exec_action(git_repository_id: int, args: dict[str, Union[int, str]]) -> None:
    """
    :param args: must provide: action[create, rerun, stop] & pipelines_exec_run(pipeline_id)
    """
    action, pipeline_id, branch = args["action"], args["pipelines_exec_run"], args.get("branch")
    if action == "rerun":
        return gitlab.gl_rerun_pipeline_job(git_repository_id, pipeline_id)
    elif action == "stop":
        return gitlab.gl_stop_pipeline_job(git_repository_id, pipeline_id)
    elif action == "create":
        return gitlab.create_pipeline(git_repository_id, branch)


def pipeline_exec_list(git_repository_id: int, limit: int = 10, start: int = 0) -> dict[str, Any]:
    """The list sort in descending order
    :param limit: how many data per page
    :param start: start from
    """
    pipelines_info, pagination = gitlab.gl_list_pipelines(git_repository_id, limit, start, with_pagination=True)
    ret = []
    for pipeline_info in pipelines_info:
        sha = pipeline_info["sha"]
        pipeline_info["commit_id"] = sha[:8]
        pipeline_info["commit_url"] = f'{pipeline_info["web_url"].split("/-/")[0]}/-/commit/{sha}'
        pipeline_info["execution_state"] = pipeline_info["status"].capitalize()
        pipeline_info.update(
            gitlab.get_pipeline_jobs_status(git_repository_id, pipeline_info["id"], with_commit_msg=True)
        )
        # It can not get commit message when all jobs is failed.
        if not pipeline_info["commit_message"]:
            pipeline_info["commit_message"] = gitlab.single_commit(git_repository_id, sha)["title"]
        ret.append(pipeline_info)
    return {"pagination": pagination, "pipe_execs": ret}


def get_pipeline_job_status(repo_id: int, pipeline_id: int) -> list[dict[str, Any]]:
    jobs = gitlab.gl_pipeline_jobs(repo_id, pipeline_id)
    ret = [
        {
            "stage_id": job["id"],
            "name": job["name"],
            "state": job["status"].capitalize(),
        }
        for job in jobs
    ]
    return sorted(ret, key=lambda r: r["stage_id"])


def get_pipe_log_websocket(data):
    repo_id, job_id = data["repository_id"], data["stage_id"]
    ws_start_time = time.time()
    success_end_word = "Job succeeded"
    failure_end_word = "ERROR: Job failed"
    i, last_index, first_time = 0, 0, True
    while True:
        ret = gitlab.gl_get_pipeline_console(repo_id, job_id)
        ws_end_time = time.time() - ws_start_time

        if (success_end_word in ret or failure_end_word in ret) and first_time:
            first_time = False

        if ret != "":
            # Calculate last_index, next time emit from last_index.
            ret_list = ret.split("\n")
            ret = "\n".join(ret_list[last_index:])
            last_index = len(ret_list)
        emit(
            "pipeline_log",
            {
                "data": ret,
                "repository_id": repo_id,
                "repo_id": job_id,
                "final": not first_time,
                "last_index": last_index,
            },
        )
        i += 1

        if not first_time or ws_end_time >= 600 or i >= 1000:
            i, last_index, first_time = 0, 0, True
            break


def get_ci_yaml(repository_id, branch_name):
    parameter = {"branch": branch_name}
    (
        yaml_file_can_not_find,
        yml_file_can_not_find,
        get_yaml_data,
    ) = _get_rancher_pipeline_yaml(repository_id, parameter)
    if yaml_file_can_not_find and yml_file_can_not_find:
        return util.respond(204)
    rancher_ci_yaml = base64.b64decode(get_yaml_data["content"]).decode("utf-8")
    rancher_ci_json = yaml.safe_load(rancher_ci_yaml)
    return {"message": "success", "data": rancher_ci_json}, 200


def get_phase_yaml(repository_id, branch_name):
    parameter = {"branch": branch_name}
    (
        yaml_file_can_not_find,
        yml_file_can_not_find,
        get_yaml_data,
    ) = _get_rancher_pipeline_yaml(repository_id, parameter)
    if yaml_file_can_not_find and yml_file_can_not_find:
        return util.respond(204)

    rancher_ci_yaml = base64.b64decode(get_yaml_data["content"]).decode("utf-8")
    rancher_ci_json = yaml.safe_load(rancher_ci_yaml)
    phase_name_array = []
    phase_name = None
    for index, rancher_stage in enumerate(rancher_ci_json["stages"]):
        if "--" in rancher_stage["name"]:
            cut_list = rancher_stage["name"].split("--")
            phase_name = cut_list[0]
            soft_name = cut_list[1]
        else:
            soft_name = rancher_stage["name"]
        phase_name_array.append({"id": index + 1, "phase": phase_name, "software": soft_name})
    return {"message": "success", "data": phase_name_array}, 200


def _get_rancher_pipeline_yaml(repository_id, parameter):
    yaml_file_can_not_find = None
    yml_file_can_not_find = None
    get_yaml_data = None
    get_file_param = dict(parameter)
    try:
        get_file_param["file_path"] = ".rancher-pipeline.yaml"
        get_yaml_data = gitlab.gl_get_project_file_for_pipeline(repository_id, get_file_param).json()
        parameter["file_path"] = ".rancher-pipeline.yaml"
    except apiError.DevOpsError as e:
        if e.status_code == 404:
            yaml_file_can_not_find = True
    try:
        get_file_param["file_path"] = ".rancher-pipeline.yml"
        get_yaml_data = gitlab.gl_get_project_file_for_pipeline(repository_id, get_file_param).json()
        parameter["file_path"] = ".rancher-pipeline.yml"
    except apiError.DevOpsError as e:
        if e.status_code == 404:
            yml_file_can_not_find = True
    return yaml_file_can_not_find, yml_file_can_not_find, get_yaml_data


def check_pipeline_folder_exist(file_name, path):
    if file_name not in listdir(path):
        raise apiError.DevOpsError(
            404,
            "The file is not found in provided path.",
            apiError.file_not_found(file_name, path),
        )


def list_pipeline_file(project_name):
    project_folder_path = f"devops-data/project-data/{project_name}/pipeline"
    return {folder: listdir(f"{project_folder_path}/{folder}") for folder in listdir(project_folder_path)}


def upload_pipeline_file(project_name, folder_name, file):
    file_path = f"devops-data/project-data/{project_name}/pipeline/{folder_name}"
    makedirs(file_path, exist_ok=True)
    file.save(f"{file_path}/{file.filename}")


def download_pipeline_file(project_name, folder_name, file_name):
    file_path = f"devops-data/project-data/{project_name}/pipeline/{folder_name}"
    check_pipeline_folder_exist(file_name, file_path)
    return send_file(f"../{file_path}/{file_name}")


def delete_pipeline_file(project_name, folder_name, file_name):
    file_path = f"devops-data/project-data/{project_name}/pipeline/{folder_name}"
    check_pipeline_folder_exist(file_name, file_path)
    rmtree(file_path)


# --------------------- Resources ---------------------


class PipelineExec(Resource):
    @jwt_required()
    def get(self, repository_id):
        parser = reqparse.RequestParser()
        parser.add_argument("limit", default=10, type=int, location="args")
        parser.add_argument("start", default=0, type=int, location="args")
        args = parser.parse_args()
        return util.success(pipeline_exec_list(repository_id, args["limit"], args["start"]))
        # return util.success(gitlab.gl_get_pipeline_console(repository_id, args["limit"]))


class PipelineExecAction(Resource):
    @jwt_required()
    def post(self, repository_id):
        parser = reqparse.RequestParser()
        parser.add_argument("pipelines_exec_run", type=str, required=True)
        parser.add_argument("action", type=str, required=True)
        parser.add_argument("branch", type=str)
        args = parser.parse_args()
        return pipeline_exec_action(repository_id, args)


class PipelineConfig(Resource):
    @jwt_required()
    def get(self, repository_id):
        parser = reqparse.RequestParser()
        parser.add_argument("pipelines_exec_run", type=int, required=True, location="args")
        args = parser.parse_args()
        return get_pipeline_job_status(repository_id, args["pipelines_exec_run"])


# ----------------------------------------------------------------------------------------------------------------------------


class PipelineExecLogs(Resource):
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument("repository_id", type=int, required=True, location="args")
        parser.add_argument("pipelines_exec_run", type=int, required=True, location="args")
        args = parser.parse_args()
        # return pipeline_exec_logs(args)
        return util.success()


class PipelineYaml(Resource):
    @jwt_required()
    def get(self, repository_id, branch_name):
        return get_ci_yaml(repository_id, branch_name)


class PipelinePhaseYaml(Resource):
    @jwt_required()
    def get(self, repository_id, branch_name):
        return get_phase_yaml(repository_id, branch_name)


class Pipeline(Resource):
    @jwt_required()
    def post(self, repository_id):
        role.require_in_project(repository_id=repository_id)
        parser = reqparse.RequestParser()
        parser.add_argument("branch", type=str, required=True, location="form")
        args = parser.parse_args()
        gitlab.create_pipeline(repository_id, args["branch"])
        return util.success()


class PipelineFile(Resource):
    @jwt_required()
    def get(self, project_name):
        return util.success(list_pipeline_file(project_name))

    # Upload
    @jwt_required()
    def post(self, project_name):
        parser = reqparse.RequestParser()
        parser.add_argument("commit_short_id", type=str, required=True, location="form")
        parser.add_argument("sequence", type=int, required=True, location="form")
        parser.add_argument("upload_file", type=werkzeug.datastructures.FileStorage, location="files")
        args = parser.parse_args()
        folder_name = f'{args["commit_short_id"]}-{args["sequence"]}'
        upload_pipeline_file(project_name, folder_name, args["upload_file"])
        return util.success()

    # Download
    @jwt_required()
    def patch(self, project_name):
        parser = reqparse.RequestParser()
        parser.add_argument("commit_short_id", type=str, required=True)
        parser.add_argument("sequence", type=int, required=True)
        parser.add_argument("file_name", type=str, required=True)
        args = parser.parse_args()
        folder_name = f'{args["commit_short_id"]}-{args["sequence"]}'
        return download_pipeline_file(project_name, folder_name, args["file_name"])

    @jwt_required()
    def delete(self, project_name):
        parser = reqparse.RequestParser()
        parser.add_argument("folder_name", type=str, required=True, location="args")
        parser.add_argument("file_name", type=str, required=True, location="args")
        args = parser.parse_args()
        return util.success(delete_pipeline_file(project_name, args["folder_name"], args["file_name"]))


class PipelineWebsocketLog(Namespace):
    def on_connect(self):
        print("connect")

    def on_disconnect(self):
        print("Client disconnected")

    def on_get_pipe_log(self, data):
        print("get_pipe_log")
        get_pipe_log_websocket(data)
