# Copyright (C) 2011-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

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
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from django.conf import settings

from lava_common.exceptions import ConfigurationError
from lava_common.yaml import yaml_safe_dump, yaml_safe_load

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from typing import Any, BinaryIO, TextIO

    from lava_scheduler_app.models import TestJob


class Logs:
    def line_count(self, job: TestJob) -> int:
        raise NotImplementedError("Should implement this method")

    def open(self, job: TestJob) -> BinaryIO:
        raise NotImplementedError("Should implement this method")

    def read(self, job: TestJob, start: int = 0, end: int | None = None) -> str:
        raise NotImplementedError("Should implement this method")

    def size(self, job: TestJob, start: int = 0, end: int | None = None) -> int | None:
        raise NotImplementedError("Should implement this method")

    @contextlib.contextmanager
    def enter_writer(self, job: TestJob) -> Iterator[LogsWriter]:
        raise NotImplementedError("Should implement this method")


class LogsWriter:
    def write_line(self, line_dict: dict[str, Any], line_string: str) -> None:
        raise NotImplementedError("Should implement this method")


class LogsFilesystem(Logs):
    PACK_FORMAT = "=Q"
    PACK_SIZE = struct.calcsize(PACK_FORMAT)

    def __init__(self) -> None:
        self.index_filename = "output.idx"
        self.log_filename = "output.yaml"
        self.log_size_filename = "output.yaml.size"
        self.compressed_log_filename = "output.yaml.xz"
        super().__init__()

    def _build_index(self, job: TestJob) -> None:
        directory = pathlib.Path(job.output_dir)
        with self.open(job) as f_log:
            with open(str(directory / self.index_filename), "wb") as f_idx:
                f_idx.write(struct.pack(self.PACK_FORMAT, 0))
                line = f_log.readline()
                while line:
                    f_idx.write(struct.pack(self.PACK_FORMAT, f_log.tell()))
                    line = f_log.readline()

    def _get_line_offset(self, f_idx: BinaryIO, line: int) -> int | None:
        f_idx.seek(self.PACK_SIZE * line, 0)
        data = f_idx.read(self.PACK_SIZE)
        if data:
            return struct.unpack(self.PACK_FORMAT, data)[0]
        else:
            return None

    def line_count(self, job: TestJob) -> int:
        try:
            st = (pathlib.Path(job.output_dir) / self.index_filename).stat()
        except FileNotFoundError:
            return 0

        return int(st.st_size / self.PACK_SIZE)

    def open(self, job: TestJob) -> BinaryIO:
        directory = pathlib.Path(job.output_dir)
        with contextlib.suppress(FileNotFoundError):
            return open(str(directory / self.log_filename), "rb")
        return lzma.open(str(directory / self.compressed_log_filename), "rb")

    def read(self, job: TestJob, start: int = 0, end: int | None = None) -> str:
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

    def size(self, job: TestJob, start: int = 0, end: int | None = None) -> int | None:
        directory = pathlib.Path(job.output_dir)
        with contextlib.suppress(FileNotFoundError):
            return (directory / self.log_filename).stat().st_size
        with contextlib.suppress(FileNotFoundError, ValueError):
            return int((directory / self.log_size_filename).read_text(encoding="utf-8"))
        return None

    @contextlib.contextmanager
    def enter_writer(self, job: TestJob) -> Iterator[LogsWriter]:
        path = Path(job.output_dir)
        path.mkdir(mode=0o755, parents=True, exist_ok=True)

        with contextlib.ExitStack() as exit_stack:
            yield FilesystemLogsWriter(
                output=exit_stack.enter_context((path / self.log_filename).open("at")),
                index=exit_stack.enter_context((path / self.index_filename).open("ab")),
            )


class FilesystemLogsWriter(LogsWriter):
    def __init__(self, output: TextIO, index: BinaryIO):
        self.output = output
        self.index = index

    def write_line(self, line_dict: dict[str, Any], line_string: str) -> None:
        self.index.write(struct.pack(LogsFilesystem.PACK_FORMAT, self.output.tell()))
        self.output.write(line_string)


class LogsMongo(Logs):
    def __init__(self) -> None:
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

    def _get_docs(
        self, job: TestJob, start: int = 0, end: int | None = None
    ) -> Iterable[dict[str, Any]]:
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

    def line_count(self, job: TestJob) -> int:
        return self.db.logs.count_documents({"job_id": job.id})

    def open(self, job: TestJob) -> BinaryIO:
        stream = io.BytesIO(yaml_safe_dump(list(self._get_docs(job))).encode("utf-8"))
        stream.seek(0)
        return stream

    def read(self, job: TestJob, start: int = 0, end: int | None = None) -> str:
        docs = self._get_docs(job, start, end)
        if not docs:
            return ""

        return yaml_safe_dump(list(docs))

    def size(self, job: TestJob, start: int = 0, end: int | None = None) -> int | None:
        docs = self._get_docs(job, start, end)
        return len(yaml_safe_dump(list(docs)).encode("utf-8"))

    @contextlib.contextmanager
    def enter_writer(self, job: TestJob) -> Iterator[LogsWriter]:
        yield MongoLogsWriter(
            db=self.db,
            job_id=job.id,
        )


class MongoLogsWriter(LogsWriter):
    def __init__(self, job_id: int, db: Any):
        self.db = db
        self.job_id = job_id

    def write_line(self, line_dict: dict[str, Any], line_string: str) -> None:
        self.db.logs.insert_one(
            {
                "job_id": self.job_id,
                "dt": line_dict["dt"],
                "lvl": line_dict["lvl"],
                "msg": line_dict["msg"],
            }
        )


class LogsElasticsearch(Logs):
    MAX_RESULTS = 1000000

    def __init__(self) -> None:
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

    def _get_docs(
        self, job: TestJob, start: int = 0, end: int | None = None
    ) -> list[dict[str, str]]:
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
        if "hits" not in response:
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

    def line_count(self, job: TestJob) -> int:
        response = requests.get(
            "%s_search/" % self.api_url,
            params={"query": {"match": {"job_id": job.id}}, "_source": False},
        )
        with contextlib.suppress(Exception):
            return response["hits"]["total"]["value"]
        return 0

    def open(self, job: TestJob) -> BinaryIO:
        stream = io.BytesIO(yaml_safe_dump(self._get_docs(job)).encode("utf-8"))
        stream.seek(0)
        return stream

    def read(self, job: TestJob, start: int = 0, end: int | None = None) -> str:
        docs = self._get_docs(job, start, end)
        if not docs:
            return ""

        return yaml_safe_dump(docs)

    def size(self, job: TestJob, start: int = 0, end: int | None = None) -> int | None:
        docs = self._get_docs(job, start, end)
        return len(yaml_safe_dump(docs).encode("utf-8"))

    @contextlib.contextmanager
    def enter_writer(self, job: TestJob) -> Iterator[LogsWriter]:
        with requests.Session() as session:
            session.headers.update(self.headers)
            yield ElasticLogsWriter(
                job_id=job.id,
                api_url=self.api_url,
                session=session,
            )


class ElasticLogsWriter(LogsWriter):
    def __init__(self, job_id: int, api_url: str, session: requests.Session):
        self.job_id = job_id
        self.api_url = api_url
        self.session = session

    def write_line(self, line_dict: dict[str, Any], line_string: str) -> None:
        line_dict = line_dict.copy()
        dt = datetime.datetime.strptime(line_dict["dt"], "%Y-%m-%dT%H:%M:%S.%f")
        line_dict.update({"job_id": self.job_id, "dt": int(dt.timestamp() * 1000)})
        if line_dict["lvl"] == "results":
            line_dict.update({"msg": str(line_dict["msg"])})
        data = json_dumps(line_dict)

        self.session.post("%s_doc/" % self.api_url, data=data)


class LogsFirestore(Logs):
    def __init__(self) -> None:
        from google.cloud import firestore

        # Project ID is determined by the GCLOUD_PROJECT environment variable
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "[FILE_NAME].json"
        )
        self.db = firestore.Client()
        self.root_collection = "logs"
        super().__init__()

    def line_count(self, job: TestJob) -> int:
        doc_ref = (
            self.db.collection(self.root_collection)
            .document(
                "%02d-%02d-%02d"
                % (self.submit_time.year, self.submit_time.month, self.submit_time.day)
            )
            .collection(str(job.id))
        )
        return len(doc_ref.stream())

    def open(self, job: TestJob) -> BinaryIO:
        raise NotImplementedError("Should implement this method")

    def read(self, job: TestJob, start: int = 0, end: int | None = None) -> str:
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

    def size(self, job: TestJob, start: int = 0, end: int | None = None) -> int | None:
        # TODO: should be implemented.
        return None

    def write(
        self,
        job: TestJob,
        line: bytes,
        output: BinaryIO | None = None,
        idx: BinaryIO | None = None,
    ) -> None:
        line: dict[str, Any] = yaml_safe_load(line)[0]
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

    @contextlib.contextmanager
    def enter_writer(self, job: TestJob) -> Iterator[LogsWriter]:
        yield FirestoreLogsWriter(
            job=job,
            db=self.db,
        )


class FirestoreLogsWriter(LogsWriter):
    def __init__(self, job: TestJob, db: Any):
        self.job = job
        self.db = db

    def write_line(self, line_dict: dict[str, Any], line_string: str) -> None:
        doc_ref = (
            self.db.collection(self.root_collection)
            .document(
                "%02d-%02d-%02d"
                % (
                    self.job.submit_time.year,
                    self.job.submit_time.month,
                    self.job.submit_time.day,
                )
            )
            .collection(str(self.job.id))
            .document(line_dict["dt"])
        )
        doc_ref.set({"lvl": line_dict["lvl"], "msg": line_dict["msg"]})


logs_backend_str: str = settings.LAVA_LOG_BACKEND.rsplit(".", 1)
try:
    logs_class: type[Logs] = getattr(
        import_module(logs_backend_str[0]), logs_backend_str[1]
    )
except (AttributeError, ModuleNotFoundError) as exc:
    raise ConfigurationError(str(exc))
logs_instance: Logs = logs_class()
