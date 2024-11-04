import logging
import os

import requests
from common.config import api_key, app_insights_connection_string
from common.latency import set_simulator_translations_latency
from common.locust_app_insights import (
    report_request_metric,
)
from locust import HttpUser, constant, events, task
from locust.env import Environment

max_tokens = 100
deployment_name = os.getenv("DEPLOYMENT_NAME", None)

if deployment_name is None:
    raise ValueError("DEPLOYMENT_NAME environment variable must be set")


@events.init.add_listener
def on_locust_init(environment: Environment, **_):
    """
    Configure test
    """
    if app_insights_connection_string:
        logging.info("App Insights connection string found - enabling request metrics")
        environment.events.request.add_listener(report_request_metric)
    else:
        logging.warning("App Insights connection string not found - request metrics disabled")

    logging.info("on_locust_init: %s", environment.host)
    logging.info("Using max_tokens = %d", max_tokens)

    logging.info("Set chat completion latencies to 10ms per token (~1s latency)")
    logging.info("Set translation latencies to 830ms per 1MB (~1s latency for a 1.6MB audio file)")
    set_simulator_translations_latency(environment.host, mean=625, std_dev=0.1)

    # initial request to warm up the deployment (to avoid cold start being included in the latency)
    with open(".audio/short-white-noise.mp3", "rb") as f:
        requests.post(
            environment.host + "/openai/deployments/" + deployment_name + "/audio/translations?api-version=2023-05-15",
            headers={"api-key": api_key},
            files={"file": f},
            data={
                "response_format": "json",
            },
            timeout=10,
        )

    logging.info("on_locust_init - done")


class TranslationsUser(HttpUser):
    wait_time = constant(1)  # wait 1 second between requests

    @task
    def hello_world(self):
        global got_429_errors, got_other_errors

        url = f"openai/deployments/{deployment_name}/audio/translations?api-version=2023-05-15"
        with open(".audio/short-white-noise.mp3", "rb") as f:
            response = self.client.post(
                url,
                headers={"api-key": api_key},
                files={"file": f},
                data={
                    "response_format": "json",
                },
            )
            if response.status_code >= 300:
                if response.status_code == 429:
                    got_429_errors = True
                else:
                    got_other_errors = True
