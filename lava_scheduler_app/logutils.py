# Copyright (C) 2011-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import datetime
import io
import json
import lzma
import os
import pathlib
import struct
from importlib import import_module
from json import dumps as json_dumps
from json import loads as json_loads

import requests
from django.conf import settings

from lava_common.exceptions import ConfigurationError
from lava_common.yaml import yaml_safe_dump, yaml_safe_load


class Logs:
    def line_count(self, job):
        raise NotImplementedError("Should implement this method")

    def open(self, job):
        raise NotImplementedError("Should implement this method")

    def read(self, job, start=0, end=None):
        raise NotImplementedError("Should implement this method")

    def size(self, job, start=0, end=None):
        raise NotImplementedError("Should implement this method")

    def write(self, job, line, output=None, idx=None):
        raise NotImplementedError("Should implement this method")


class LogsFilesystem(Logs):
    PACK_FORMAT = "=Q"
    PACK_SIZE = struct.calcsize(PACK_FORMAT)

    def __init__(self):
        self.index_filename = "output.idx"
        self.log_filename = "output.yaml"
        self.log_size_filename = "output.yaml.size"
        self.compressed_log_filename = "output.yaml.xz"
        super().__init__()

    def _build_index(self, job):
        directory = pathlib.Path(job.output_dir)
        with self.open(job) as f_log:
            with open(str(directory / self.index_filename), "wb") as f_idx:
                f_idx.write(struct.pack(self.PACK_FORMAT, 0))
                line = f_log.readline()
                while line:
                    f_idx.write(struct.pack(self.PACK_FORMAT, f_log.tell()))
                    line = f_log.readline()

    def _get_line_offset(self, f_idx, line):
        f_idx.seek(self.PACK_SIZE * line, 0)
        data = f_idx.read(self.PACK_SIZE)
        if data:
            return struct.unpack(self.PACK_FORMAT, data)[0]
        else:
            return None

    def line_count(self, job):
        st = (pathlib.Path(job.output_dir) / self.index_filename).stat()
        return int(st.st_size / self.PACK_SIZE)

    def open(self, job):
        directory = pathlib.Path(job.output_dir)
        with contextlib.suppress(FileNotFoundError):
            return open(str(directory / self.log_filename), "rb")
        return lzma.open(str(directory / self.compressed_log_filename), "rb")

    def read(self, job, start=0, end=None):
        directory = pathlib.Path(job.output_dir)

        # Only create the index if needed
        if start == 0 and end is None:
            with self.open(job) as f_log:
                return f_log.read().decode("utf-8")

        # Create the index
        if not (directory / self.index_filename).exists():
            self._build_index(job)
        # use it now
        with open(str(directory / self.index_filename), "rb") as f_idx:
            start_offset = self._get_line_offset(f_idx, start)
            if start_offset is None:
                return ""
            with self.open(job) as f_log:
                f_log.seek(start_offset)
                if end is None:
                    return f_log.read().decode("utf-8")
                end_offset = self._get_line_offset(f_idx, end)
                if end_offset is None:
                    return f_log.read().decode("utf-8")
                if end_offset <= start_offset:
                    return ""
                return f_log.read(end_offset - start_offset).decode("utf-8")

    def size(self, job):
        directory = pathlib.Path(job.output_dir)
        with contextlib.suppress(FileNotFoundError):
            return (directory / self.log_filename).stat().st_size
        with contextlib.suppress(FileNotFoundError, ValueError):
            return int((directory / self.log_size_filename).read_text(encoding="utf-8"))
        return None

    def write(self, job, line, output=None, idx=None):
        idx.write(struct.pack(self.PACK_FORMAT, output.tell()))
        idx.flush()
        output.write(line)
        output.flush()


class LogsMongo(Logs):
    def __init__(self):
        import pymongo

        self.client = pymongo.MongoClient(settings.MONGO_DB_URI)
        try:
            # Test connection.
            # The ismaster command is cheap and does not require auth.
            self.client.admin.command("ismaster")
        except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
            raise ConfigurationError(
                "MongoDB URI is not configured properly. Unable to connect to MongoDB."
            )

        self.db = self.client[settings.MONGO_DB_DATABASE]
        self.db.logs.create_index([("job_id", 1), ("dt", 1)])
        super().__init__()

    def _get_docs(self, job, start=0, end=None):
        import pymongo

        limit = 0
        if end:
            limit = end - start
        if limit < 0:
            return []

        return self.db.logs.find(
            filter={"job_id": job.id},
            projection={"_id": False, "job_id": False},
            sort=[("dt", pymongo.ASCENDING)],
            skip=start,
            limit=limit,
        )

    def line_count(self, job):
        return self.db.logs.count_documents({"job_id": job.id})

    def open(self, job):
        stream = io.BytesIO(yaml_safe_dump(list(self._get_docs(job))).encode("utf-8"))
        stream.seek(0)
        return stream

    def read(self, job, start=0, end=None):
        docs = self._get_docs(job, start, end)
        if not docs:
            return ""

        return yaml_safe_dump(list(docs))

    def size(self, job, start=0, end=None):
        docs = self._get_docs(job, start, end)
        return len(yaml_safe_dump(list(docs)).encode("utf-8"))

    def write(self, job, line, output=None, idx=None):
        line = yaml_safe_load(line)[0]

        self.db.logs.insert_one(
            {"job_id": job.id, "dt": line["dt"], "lvl": line["lvl"], "msg": line["msg"]}
        )


class LogsElasticsearch(Logs):
    MAX_RESULTS = 1000000

    def __init__(self):
        self.api_url = "%s%s/" % (
            settings.ELASTICSEARCH_URI,
            settings.ELASTICSEARCH_INDEX,
        )
        self.headers = {"Content-type": "application/json"}
        if settings.ELASTICSEARCH_APIKEY:
            self.headers.update(
                {"Authorization": "ApiKey %s" % settings.ELASTICSEARCH_APIKEY}
            )
        params = {
            "settings": {"index": {"max_result_window": self.MAX_RESULTS}},
            "mappings": {"properties": {"dt": {"type": "date"}}},
        }
        requests.put(self.api_url, json_dumps(params), headers=self.headers)
        super().__init__()

    def _get_docs(self, job, start=0, end=None):
        if not end:
            end = self.MAX_RESULTS

        limit = end - start
        if limit < 0:
            return []

        params = {
            "query": {"match": {"job_id": job.id}},
            "from": start,
            "size": limit,
            "sort": [{"dt": {"order": "asc"}}],
        }

        response = requests.get(
            "%s_search/" % self.api_url,
            data=json_dumps(params),
            headers=self.headers,
        )

        response = json_loads(response.text)
        if not "hits" in response:
            return []
        result = []
        for res in response["hits"]["hits"]:
            doc = res["_source"]
            doc.update(
                {"dt": datetime.datetime.fromtimestamp(doc["dt"] / 1000.0).isoformat()}
            )
            if doc["lvl"] == "results":
                doc.update({"msg": yaml_safe_load(doc["msg"])})
            result.append(doc)
        return result

    def line_count(self, job):
        response = requests.get(
            "%s_search/" % self.api_url,
            params={"query": {"match": {"job_id": job.id}}, "_source": False},
        )
        with contextlib.suppress(Exception):
            return response["hits"]["total"]["value"]
        return 0

    def open(self, job):
        stream = io.BytesIO(yaml_safe_dump(self._get_docs(job)).encode("utf-8"))
        stream.seek(0)
        return stream

    def read(self, job, start=0, end=None):
        docs = self._get_docs(job, start, end)
        if not docs:
            return ""

        return yaml_safe_dump(docs)

    def size(self, job, start=0, end=None):
        docs = self._get_docs(job, start, end)
        return len(yaml_safe_dump(docs).encode("utf-8"))

    def write(self, job, line, output=None, idx=None):
        line = yaml_safe_load(line)[0]
        dt = datetime.datetime.strptime(line["dt"], "%Y-%m-%dT%H:%M:%S.%f")
        line.update({"job_id": job.id, "dt": int(dt.timestamp() * 1000)})
        if line["lvl"] == "results":
            line.update({"msg": str(line["msg"])})
        data = json_dumps(line)

        requests.post("%s_doc/" % self.api_url, data=data, headers=self.headers)


class LogsFirestore(Logs):
    def __init__(self):
        from google.cloud import firestore

        # Project ID is determined by the GCLOUD_PROJECT environment variable
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "[FILE_NAME].json"
        )
        self.db = firestore.Client()
        self.root_collection = "logs"
        super().__init__()

    def line_count(self, job):
        doc_ref = (
            self.db.collection(self.root_collection)
            .document(
                "%02d-%02d-%02d"
                % (self.submit_time.year, self.submit_time.month, self.submit_time.day)
            )
            .collection(str(job.id))
        )
        return len(doc_ref.stream())

    def open(self, job):
        raise NotImplementedError("Should implement this method")

    def read(self, job, start=0, end=None):
        # TODO: read() method should utilize start and end numbers.
        docs = (
            self.db.collection(self.root_collection)
            .document(
                "%02d-%02d-%02d"
                % (job.submit_time.year, job.submit_time.month, job.submit_time.day)
            )
            .collection(str(job.id))
            .limit(end)
            .stream()
        )
        result = []
        for doc in docs:
            doc_dict = doc.to_dict()
            result.append(
                json.dumps(
                    {"dt": doc.id, "lvl": doc_dict["lvl"], "msg": doc_dict["msg"]}
                )
            )
        return "\n".join(["- %s" % x for x in result])

    def size(self, job, start=0, end=None):
        # TODO: should be implemented.
        return None

    def write(self, job, line, output=None, idx=None):
        line = yaml_safe_load(line)[0]
        doc_ref = (
            self.db.collection(self.root_collection)
            .document(
                "%02d-%02d-%02d"
                % (job.submit_time.year, job.submit_time.month, job.submit_time.day)
            )
            .collection(str(job.id))
            .document(line["dt"])
        )
        doc_ref.set({"lvl": line["lvl"], "msg": line["msg"]})


logs_backend_str = settings.LAVA_LOG_BACKEND.rsplit(".", 1)
try:
    logs_class = getattr(import_module(logs_backend_str[0]), logs_backend_str[1])
except (AttributeError, ModuleNotFoundError) as exc:
    raise ConfigurationError(str(exc))
logs_instance = logs_class()
