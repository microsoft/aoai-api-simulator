import os

api_key = os.getenv("API_KEY", os.getenv("SIMULATOR_API_KEY"))
opentelemetry_exporter_otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
applicationinsights_connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
log_analytics_workspace_id = os.getenv("LOG_ANALYTICS_WORKSPACE_ID")
log_analytics_workspace_name = os.getenv("LOG_ANALYTICS_WORKSPACE_NAME")
tenant_id = os.getenv("TENANT_ID")
subscription_id = os.getenv("SUBSCRIPTION_ID")
resource_group_name = os.getenv("RESOURCE_GROUP_NAME")
