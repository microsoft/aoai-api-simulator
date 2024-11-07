import logging

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import metrics

from .config import (
    applicationinsights_connection_string,
)

histogram_request_latency: metrics.Histogram

if applicationinsights_connection_string:
    # Options: https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/monitor/azure-monitor-opentelemetry#usage
    logging.getLogger("azure").setLevel(logging.WARNING)
    configure_azure_monitor(connection_string=applicationinsights_connection_string)
    histogram_request_latency = metrics.get_meter(__name__).create_histogram(
        "locust.request_latency", "Request latency", "s"
    )


def report_request_metric(request_type, name, response_time, response_length, exception, **kwargs):
    if not exception:
        # response_time is in milliseconds
        response_time_s = response_time / 1000
        histogram_request_latency.record(response_time_s)
