import logging
import os

from aoai_api_simulator.app_builder import app as builder_app
from aoai_api_simulator.app_builder import apply_config

# from opentelemetry import trace
from aoai_api_simulator.config_loader import get_config_from_env_vars, set_config
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

#  from opentelemetry.sdk._logs.export import ConsoleLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

log_level = os.getenv("LOG_LEVEL") or "INFO"

logger = logging.getLogger(__name__)
logging.basicConfig(level=log_level)
logging.getLogger("azure").setLevel(logging.WARNING)

opentelemetry_exporter_otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
application_insights_connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

using_azure_monitor: bool

if application_insights_connection_string:
    logger.info("🚀 Configuring Azure Monitor telemetry")

    # Options: https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/monitor/azure-monitor-opentelemetry#usage
    configure_azure_monitor(connection_string=application_insights_connection_string)
    using_azure_monitor = True
else:
    using_azure_monitor = False
    logger.info("🚀 Azure Monitor telemetry not configured (set APPLICATIONINSIGHTS_CONNECTION_STRING)")

    if opentelemetry_exporter_otlp_endpoint:
        logger.info("🚀 Configuring OTLP telemetry")

        # setup the instrumentors
        resource = Resource(attributes={"service.name": "aoai-api-simulator"})

        trace.set_tracer_provider(TracerProvider(resource=resource))
        tracer = trace.get_tracer(__name__)

        # https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-configuration?tabs=python#enable-the-otlp-exporter

        otlp_exporter = OTLPSpanExporter(endpoint=opentelemetry_exporter_otlp_endpoint)

        # tracing
        tracer = trace.get_tracer(__name__)
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)

        # metrics
        reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=opentelemetry_exporter_otlp_endpoint))
        meterProvider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meterProvider)

        # logging
        logger_provider = LoggerProvider(
            resource=resource,
        )

        otlp_exporter = OTLPLogExporter(endpoint=opentelemetry_exporter_otlp_endpoint)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))

        handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
        # Attach OTLP handler to root logger
        logging.getLogger().addHandler(handler)
    else:
        logger.info("🚀 OTLP telemetry exporter not configured (set OTEL_EXPORTER_OTLP_ENDPOINT)")

config = get_config_from_env_vars(logger)
set_config(config)

apply_config()

app = builder_app  # expose to gunicorn

if not using_azure_monitor:
    FastAPIInstrumentor.instrument_app(app)
