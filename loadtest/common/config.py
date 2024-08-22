import os

api_key = os.getenv("API_KEY", os.getenv("SIMULATOR_API_KEY"))
app_insights_connection_string = os.getenv("APP_INSIGHTS_CONNECTION_STRING")
log_analytics_workspace_id = os.getenv("LOG_ANALYTICS_WORKSPACE_ID")
log_analytics_workspace_name = os.getenv("LOG_ANALYTICS_WORKSPACE_NAME")
tenant_id = os.getenv("TENANT_ID")
subscription_id = os.getenv("SUBSCRIPTION_ID")
resource_group_name = os.getenv("RESOURCE_GROUP_NAME")
