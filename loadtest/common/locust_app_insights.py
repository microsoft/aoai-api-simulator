import logging
from opentelemetry import metrics
from azure.monitor.opentelemetry import configure_azure_monitor

from .config import (
    app_insights_connection_string,
)


histogram_request_latency: metrics.Histogram

if app_insights_connection_string:
    # Options: https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/monitor/azure-monitor-opentelemetry#usage
    logging.getLogger("azure").setLevel(logging.WARNING)
    configure_azure_monitor(connection_string=app_insights_connection_string)
    histogram_request_latency = metrics.get_meter(__name__).create_histogram(
        "locust.request_latency", "Request latency", "s"
    )


def report_request_metric(request_type, name, response_time, response_length, exception, **kwargs):
    if not exception:
        # response_time is in milliseconds
        response_time_s = response_time / 1000
        histogram_request_latency.record(response_time_s)
