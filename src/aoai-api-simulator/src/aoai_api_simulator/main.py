from aoai_api_simulator.app_builder import app as builder_app
from aoai_api_simulator.app_builder import apply_config

# from opentelemetry import trace
from aoai_api_simulator.config_loader import get_config_from_env_vars, set_config
from aoai_api_simulator.telemetry import setup_auto_instrumentation, setup_telemetry

using_azure_monitor: bool = setup_telemetry()

config = get_config_from_env_vars()
set_config(config)
apply_config()

app = builder_app  # expose to gunicorn
setup_auto_instrumentation(app, using_azure_monitor)
