import logging
import os

import yaml
from fastapi.datastructures import URL

from .models import RecordedResponse, hash_body, hash_request_parts

logger = logging.getLogger(__name__)


class YamlRecordingPersister:
    def __init__(self, recording_dir: str):
        self._recording_dir = recording_dir

    def save_recording(self, url: str, recording: dict[int, RecordedResponse]):
        interactions = []
        for recorded_response in recording.values():
            request = recorded_response.full_request
            # skip the full body for large requests (ensure we have a hash)
            if "body" in request:
                if "body_hash" not in request:
                    request["body_hash"] = hash_body(request["headers"], request["body"])

                if len(request.get("body") or "") > 1024:
                    request["body"] = None

            interaction = {
                "request": request,
                "response": {
                    "status": {"code": recorded_response.status_code},
                    "headers": recorded_response.headers,
                    "body": {"string": recorded_response.body},
                    "duration_ms": recorded_response.duration_ms,
                },
                "context_values": recorded_response.context_values,
            }
            interactions.append(interaction)
        recording_data = {"interactions": interactions, "version": 1}

        recording_path = self.get_recording_file_path(url)
        self.ensure_recording_dir_exists()
        with open(recording_path, "w", encoding="utf-8") as f:
            yaml.dump(recording_data, stream=f, Dumper=yaml.CDumper)
        logger.info("💾 Recording saved to %s", recording_path)

    def ensure_recording_dir_exists(self):
        if not os.path.exists(self._recording_dir):
            os.mkdir(self._recording_dir)

    def get_recording_file_path(self, url: str):
        query_start = url.find("?")
        if query_start != -1:
            url = url[:query_start]
        recording_file_name = url.strip("/").replace("/", "_") + ".yaml"
        recording_file_path = os.path.join(self._recording_dir, recording_file_name)
        return recording_file_path

    def load_recording_for_url(self, url: str, expect_recording_file: bool):
        recording_file_path = self.get_recording_file_path(url)
        if not os.path.exists(recording_file_path):
            if expect_recording_file:
                logger.warning("No recording file found at %s", recording_file_path)
            return None

        with open(recording_file_path, "r", encoding="utf-8") as f:
            recording_data = yaml.load(f, Loader=yaml.CLoader)
            interactions = recording_data["interactions"]
            recording = {}
            for interaction in interactions:
                request = interaction["request"]
                response = interaction["response"]
                uri_string = request["uri"]
                # Allow for old recordings without body hash (or edited recordings with just the body)
                # Also handle large recordings that omit the body and only have the hash
                if "body_hash" not in request:
                    if "body" not in request:
                        raise ValueError(f"No body or body hash found in recording for request {uri_string}")
                    request["body_hash"] = hash_body(request["headers"], request["body"])

                request_hash = hash_request_parts(
                    request["method"],
                    # parse URL to get path without host for matching against incoming request
                    URL(uri_string).path,
                    request["headers"],
                    body_hash=request["body_hash"],
                )
                context_values = interaction.get("context_values", {})

                recording[request_hash] = RecordedResponse(
                    request_hash=request_hash,
                    status_code=response["status"]["code"],
                    headers=response["headers"],
                    body=response["body"].get("string"),
                    context_values=context_values,
                    full_request=request,
                    duration_ms=response.get("duration_ms", 0),  # didn't exist in earlier recordings so default to 0
                )
            return recording
