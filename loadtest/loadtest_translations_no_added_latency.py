import logging
import os

from common.config import api_key, app_insights_connection_string
from common.latency import set_simulator_translations_latency
from common.locust_app_insights import (
    report_request_metric,
)
from locust import HttpUser, constant, events, task
from locust.env import Environment

deployment_name = os.getenv("DEPLOYMENT_NAME", None)
allow_429_responses = os.getenv("ALLOW_429_RESPONSES", "false").lower() == "true"

if deployment_name is None:
    raise ValueError("DEPLOYMENT_NAME environment variable must be set")

got_429_errors = False
got_other_errors = False


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
    logging.info("Using deployment_name = %s", deployment_name)
    logging.info("Using allow_429_responses = %s", allow_429_responses)

    logging.info("Set translation latencies to zero")
    set_simulator_translations_latency(environment.host, mean=0, std_dev=0)

    logging.info("on_locust_init - done")


@events.quitting.add_listener
def _(environment: Environment, **_):
    if got_429_errors and allow_429_responses:
        if got_other_errors:
            logging.info("allow_429s is set but got other errors - leaving exit code")
        else:
            # Set the exit code to 0 if we only got 429s and allow_429s is set
            logging.info("allow_429s is set but got other errors - overriding exit code to 0")
            environment.process_exit_code = 0


class TranslationsUser(HttpUser):
    wait_time = constant(1)  # wait 1 second between requests

    @task
    def hello_world(self):
        global got_429_errors, got_other_errors

        url = f"openai/deployments/{deployment_name}/audio/translations?api-version=2023-05-15"
        response = self.client.post(
            url,
            headers={"api-key": api_key},
            files={"file": open(".audio/short-white-noise.mp3", "rb")},
            data={
                "response_format": "json",
            },
        )
        if response.status_code >= 300:
            if response.status_code == 429:
                got_429_errors = True
            else:
                got_other_errors = True
