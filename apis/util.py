import json
import os
import secrets
import string
import time
import math
from datetime import datetime, date, timedelta
from datetime import time as d_time
from threading import Thread
import paramiko

import requests
from flask_restful import reqparse
from paramiko.client import SSHClient
from paramiko.rsakey import RSAKey

from resources import logger

import resources.apiError as apiError
import base64
from marshmallow import Schema, fields

security_params = [{"bearer": []}]

import pandas as pd


def base64decode(value):
    return str(base64.b64decode(str(value)).decode("utf-8"))


def base64encode(value):
    return base64.b64encode(bytes(str(value), encoding="utf-8")).decode("utf-8")


def ssh_to_node_by_key(command, node_ip) -> tuple[str, str]:
    pkey: RSAKey = paramiko.RSAKey.from_private_key_file("./deploy-config/id_rsa")
    client: SSHClient = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=node_ip, port=22, username="rkeuser", pkey=pkey)

    stdin, stdout, stderr = client.exec_command(command)
    output_str: str = stdout.read().decode().strip()
    error_str: str = stderr.read().decode().strip()
    client.close()
    return output_str, error_str


def date_to_str(data):
    if data is not None:
        return data.isoformat()
    else:
        return None


def is_dummy_project(project_id):
    if type(project_id == str):
        return int(project_id) == -1
    else:
        return project_id == -1


# Return 200 and success message, can with data.
# If the data may contain date or other non-JSON-serializable objects, turn has_date_etc True.
# If you need to return 201, 204 or other success, use #respond.
def success(data=None, has_date_etc=False):
    if data is None:
        return {"message": "success"}, 200
    else:
        if has_date_etc:
            return {
                "message": "success",
                "data": json.loads(json.dumps(data, cls=DateEncoder)),
                "datetime": datetime.utcnow().isoformat(),
            }, 200
        else:
            return {
                "message": "success",
                "data": data,
                "datetime": datetime.utcnow().isoformat(),
            }, 200


def respond(status_code, message=None, data=None, error=None):
    if message is None:
        return None, status_code
    message_obj = {"message": message}
    if data is not None:
        if type(data) is dict:
            message_obj["data"] = json.loads(json.dumps(data, cls=DateEncoder))
        else:
            try:
                message_obj["data"] = json.loads(data)
            except (ValueError, TypeError):
                message_obj["data"] = data
    if error is not None:
        message_obj["error"] = error
    return message_obj, status_code


def respond_request_style(status_code, message=None, data=None, error=None):
    ret = respond(status_code, message, data, error)
    ret[0]["status_code"] = ret[1]
    return ret[0]


def respond_uncaught_exception(exception, message="An uncaught exception occurs:"):
    return respond(500, message, error=apiError.uncaught_exception(exception))


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return str(obj)
        else:
            return json.JSONEncoder.default(self, obj)


ticker = 0


def reset_ticker():
    global ticker
    ticker = time.time()


def tick(message="", init=False, use_logger=False):
    global ticker
    now = time.time()
    if init:
        if message:
            print(message)
            if use_logger:
                logger.logger.info(message)
        ticker = now
        return
    elapsed = now - ticker
    print("%f seconds elapsed. [%s]" % (elapsed, message))
    if use_logger:
        logger.logger.info("%f seconds elapsed. [%s]" % (elapsed, message))
    ticker = now
    return elapsed


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        ret = method(*args, **kw)
        te = time.time()
        print(f"{method.__name__} %2.2f ms" % ((te - ts) * 1000))
        return ret

    return timed


def api_request(method, url, headers=None, params=None, data=None, auth=None):
    body = data
    if type(data) is dict or type(data) is reqparse.Namespace:
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        if headers["Content-Type"] == "application/json" and body is not None:
            body = json.dumps(data)

    if method.upper() == "GET":
        return requests.get(url, headers=headers, params=params, verify=False, auth=auth)
    elif method.upper() == "POST":
        return requests.post(url, data=body, params=params, headers=headers, verify=False, auth=auth)
    elif method.upper() == "PUT":
        return requests.put(url, data=body, params=params, headers=headers, verify=False, auth=auth)
    elif method.upper() == "DELETE":
        return requests.delete(url, headers=headers, params=params, verify=False, auth=auth)
    else:
        return respond_request_style(
            500,
            "Error while request {0} {1}".format(method, url),
            error=apiError.invalid_code_path("Only GET/PUT/POST/DELETE is allowed, but" "{0} provided.".format(method)),
        )


def check_url_alive(url, is_200=False):
    import requests

    try:
        if is_200:
            alive = requests.get(url, verify=False, timeout=20).status_code < 400
        else:
            alive = requests.get(url, verify=False, timeout=20).status_code < 500
    except Exception:
        alive = False
    return alive


def encode_k8s_sa(name):
    ret = ""
    for c in name:
        if "a" <= c <= "z" or "1" <= c <= "9" or c == "-" or c == ".":
            ret += c
        elif "A" <= c <= "Z":
            ret += c.lower() + "0"
        elif c == "0":
            ret += "00"
        elif c == "_":
            ret += "-0"
    return ret


def merge_zero(c):
    if c == "0":
        return "0"
    elif c == "-":
        return "_"
    else:
        return c.upper()


def decode_k8s_sa(string):
    ret = ""
    i = 0
    while i < len(string):
        c = string[i]
        if i == len(string) - 1:
            ret += c
            i += 1
            continue
        n = string[i + 1]
        if n == "0":
            nn = i + 2
            zero_count = 1
            while nn < len(string):
                if string[nn] == "0":
                    nn += 1
                    zero_count += 1
                else:
                    break
            if zero_count % 2 == 1:
                ret += merge_zero(c)
                i += 2
                zero_count -= 1
            else:
                ret += c
                i += 1
            for _ in range(0, int(zero_count / 2)):
                ret += "0"
                i += 2
        else:
            ret += c
            i += 1
    return ret


def get_random_alphanumeric_string(letters_count_each, digits_count):
    # Secrets is more recommended insecure functions
    sample_str = "".join((secrets.choice(string.ascii_lowercase) for _ in range(letters_count_each)))
    sample_str += "".join((secrets.choice(string.ascii_uppercase) for _ in range(letters_count_each)))
    sample_str += "".join((secrets.choice(string.digits) for _ in range(digits_count)))
    return sample_str


def check_json(string):
    try:
        json.loads(string)
    except ValueError:
        return False
    return True


def row_to_dict(row):
    ret = {}
    if row is None:
        return row
    for key in type(row).__table__.columns.keys():
        value = getattr(row, key)
        if type(value) is datetime or type(value) is date:
            ret[key] = str(value)
        elif isinstance(value, str) and check_json(value):
            ret[key] = json.loads(value)
        else:
            ret[key] = value
    return ret


def rows_to_list(rows):
    out = []
    for row in rows:
        out.append(row_to_dict(row))
    return out


def get_pagination(total_count, limit, offset):
    page = math.ceil(float(offset) / limit)
    if offset % limit == 0:
        page += 1
    pages = math.ceil(float(total_count) / limit)
    page_dict = {
        "current": page,
        "prev": page - 1 if page - 1 > 0 else None,
        "next": page + 1 if page + 1 <= pages else None,
        "pages": pages,
        "limit": limit,
        "offset": offset,
        "total": total_count,
    }
    return page_dict


def orm_pagination(base_query, limit, offset):
    total_count = base_query.count()
    page_dict = get_pagination(total_count, limit, offset)
    if limit:
        base_query = base_query.limit(limit)
    if offset:
        base_query = base_query.offset(offset)
    return base_query, page_dict


def list_pagination(out_list, limit, offset):
    if limit is None:
        limit = 10
    if offset is None:
        offset = 0
    page_dict = get_pagination(len(out_list), limit, offset)
    if (limit - offset) <= len(out_list):
        out_list = out_list[offset : offset + limit]
    return out_list, page_dict


class DevOpsThread(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None):
        if kwargs is None:
            kwargs = {}
        Thread.__init__(self, group, target, name, args, kwargs)
        self._return = None
        self.error = None

    def run(self):
        # _target, _args, _kwargs are in the superclass Thread
        if self._target is not None:
            try:
                self._return = self._target(*self._args, **self._kwargs)
            except Exception as e:
                self.error = e

    def join_(self, *args):
        Thread.join(self, *args)
        if self.error:
            raise self.error
        return self._return


class ServiceBatchOpHelper:
    def __init__(self, services, targets, service_args):
        self.services = services
        self.targets = targets
        self.service_args = service_args
        self.errors = {}
        self.outputs = {}

    def run(self):
        threads = {}
        for service in self.services:
            self.errors[service] = None
            threads[service] = DevOpsThread(target=self.targets[service], args=self.service_args[service])
            threads[service].start()

        for service in self.services:
            try:
                self.outputs[service] = threads[service].join_()
            except Exception as e:
                self.errors[service] = e


def get_certain_date_from_now(days):
    return datetime.combine((datetime.utcnow() - timedelta(days=days)), d_time(00, 00))


def get_few_months_ago_utc_datetime(units, value_key):
    if value_key == "months":
        units = units * 30
    elif value_key == "years":
        units = units * 365
    save_time = datetime.utcnow() - timedelta(days=units)
    save_time = save_time.strftime("%Y-%m-%d %H:00:00")
    return save_time


class obj:
    def __init__(self, dict1):
        self.__dict__.update(dict1)


def read_txt(path):
    with open(path, "r") as f:
        line_list = f.readlines()
    return line_list


def read_json_file(path, return_obj=False):
    with open(path, "r") as f:
        if return_obj:
            f_info = json.load(f, object_hook=obj)
        else:
            f_info = json.load(f)
    return f_info


def write_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def check_folder_exist(path, create=False):
    exist = os.path.isdir(path)
    if not exist and create:
        os.makedirs(path)
    return exist


def write_in_excel(file_path, content):
    df = pd.DataFrame(content)
    df.to_excel(file_path, index=False)


def is_json(content):
    try:
        return json.loads(content)
    except ValueError:
        return content
    except TypeError:
        return None


def model_insert_default_value(db_name, data_list):
    from model import db

    for data in data_list:
        new = db_name(**data)
        db.session.add(new)
        db.session.commit()


class CommonResponse(Schema):
    message = fields.Str(required=True)


class CommonBasicResponse(CommonResponse):
    datetime = fields.Str(required=True, example="1970-01-01T00:00:00.000000")
