import logging
import os

from azure.monitor.opentelemetry import configure_azure_monitor

# from opentelemetry import trace

from aoai_api_simulator.config_loader import get_config_from_env_vars, set_config
from aoai_api_simulator.app_builder import app as builder_app, apply_config

log_level = os.getenv("LOG_LEVEL") or "INFO"

logger = logging.getLogger(__name__)
logging.basicConfig(level=log_level)
logging.getLogger("azure").setLevel(logging.WARNING)

application_insights_connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if application_insights_connection_string:
    logger.info("🚀 Configuring Azure Monitor telemetry")

    # Options: https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/monitor/azure-monitor-opentelemetry#usage
    configure_azure_monitor(connection_string=application_insights_connection_string)
else:
    logger.info("🚀 Azure Monitor telemetry not configured (set APPLICATIONINSIGHTS_CONNECTION_STRING)")

# tracer = trace.get_tracer(__name__)

config = get_config_from_env_vars(logger)
set_config(config)


apply_config()
app = builder_app  # expose to gunicorn
