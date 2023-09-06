import os

from model import (
    NotificationMessage,
    NotificationMessageRecipient,
    Project,
    ProjectPluginRelation,
    UserPluginRelation,
    db,
)
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql import and_
from datetime import datetime
import resources.apiError as apiError
from resources.gitlab import gitlab
from resources.notification_message import (
    close_notification_message,
    create_notification_message,
)
import subprocess
from resources.logger import logger

"""
1. another way to check redeploy ip
"""


def verify_user_can_merge_into_this_branch(pj_member, mr_obj, p_branches):
    if len(p_branches) > 0:
        for protect_branch in p_branches:
            if (
                mr_obj.target_branch == protect_branch.name
                and pj_member.access_level >= protect_branch.merge_access_levels[0]["access_level"]
            ):
                return True
        return False
    else:
        return True


def is_this_not_admin_or_bot(git_user_id):
    upr_row = UserPluginRelation.query.filter_by(repository_user_id=git_user_id).first()
    if upr_row:
        from resources import user as user_py

        if user_py.get_role_id(upr_row.user_id) not in (5, 6):
            return True
    return False


def filter_and_send_notification(pj_member, mr_obj, p_branches):
    if is_this_not_admin_or_bot(pj_member.id) and verify_user_can_merge_into_this_branch(pj_member, mr_obj, p_branches):
        nm_row = NotificationMessage.query.filter_by(alert_level=201, alert_service_id=mr_obj.id).first()
        upr_row = UserPluginRelation.query.filter_by(repository_user_id=pj_member.id).first()
        if nm_row and upr_row:
            nm_rep_row = NotificationMessageRecipient.query.filter_by(message_id=nm_row.id).first()
            user_lists = nm_rep_row.type_parameter.get("user_ids")
            if upr_row.user_id not in user_lists:
                user_lists.append(upr_row.user_id)
                nm_rep_row.type_parameter.update({"user_ids": user_lists})
                flag_modified(nm_rep_row, "type_parameter")
                db.session.add(nm_rep_row)
                db.session.commit()
        else:
            if upr_row:
                args = {
                    "alert_level": 201,
                    "title": f"Review merge request: {mr_obj.title}",
                    "alert_service_id": mr_obj.id,
                    "message_parameter": {"mr_id": mr_obj.id},
                    "message": f"#### Merge request link:  \n[{mr_obj.title}]({mr_obj.web_url}), Full Link: {mr_obj.web_url}",
                    "type_ids": [3],
                    "type_parameters": {"user_ids": [upr_row.user_id]},
                }
                create_notification_message(args, user_id=1)


def system_git_commit_id():
    git_commit_id = ""
    git_tag = ""
    git_date = ""
    if os.path.exists("git_commit"):
        with open("git_commit") as f:
            git_commit_id = f.read().splitlines()[0]
    if os.path.exists("git_tag"):
        with open("git_tag") as f:
            git_tag = f.read().splitlines()[0]
    if os.path.exists("git_date"):
        with open("git_date") as f:
            git_date = datetime.strptime(f.read().splitlines()[0], "%Y-%m-%d %H:%M:%S %z").isoformat()
    return {"git_commit_id": git_commit_id, "git_tag": git_tag, "git_date": git_date}


def send_merge_request_notification():
    """
    Get all gitlab project ids
    Call gitlab get merge request information
    send notification to assignees
    """
    pj_rows = (
        db.session.query(Project, ProjectPluginRelation)
        .join(
            ProjectPluginRelation,
            and_(Project.is_lock == False, Project.id == ProjectPluginRelation.project_id),
        )
        .all()
    )
    for pj_row in pj_rows:
        if pj_row[1]:
            pj = gitlab.gl.projects.get(pj_row[1].git_repository_id)
            if pj:
                p_branches = pj.protectedbranches.list()
                mr_objs = pj.mergerequests.list(all=True)
                if mr_objs:
                    for mr_obj in mr_objs:
                        if mr_obj.state == "opened":
                            if len(mr_obj.assignees) == 0:
                                for pj_member in pj.members.list(all=True):
                                    filter_and_send_notification(pj_member, mr_obj, p_branches)
                            else:
                                for assignee in mr_obj.assignees:
                                    assignee_member = pj.members.get(assignee["id"])
                                    if verify_user_can_merge_into_this_branch(assignee_member, mr_obj, p_branches):
                                        filter_and_send_notification(assignee_member, mr_obj, p_branches)
                                    else:
                                        for pj_member in pj.members.list(all=True):
                                            filter_and_send_notification(pj_member, mr_obj, p_branches)

                        else:
                            nm_rows = NotificationMessage.query.filter_by(
                                alert_level=201, alert_service_id=mr_obj.id
                            ).all()
                            if len(nm_rows) > 0:
                                for nm_row in nm_rows:
                                    close_notification_message(nm_row.id)


def remove_unused_volume():
    """
    Remove unused volume
    """
    cmd = "docker volume ls -qf dangling=true | xargs --no-run-if-empty docker volume rm"
    result = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True, check=True)
    result = result.stdout.decode("utf-8")
    print(result)
    logger.info(f"Remove used volume: {result}")