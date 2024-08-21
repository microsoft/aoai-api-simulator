from datetime import UTC, datetime, timedelta
import os
import logging

import asciichartpy as asciichart
from azure.identity import DefaultAzureCredential

from common.config import (
    tenant_id,
    subscription_id,
    resource_group_name,
    log_analytics_workspace_id,
    log_analytics_workspace_name,
)

from common.log_analytics import QueryProcessor, Table

logging.basicConfig(level=logging.INFO)
logging.getLogger("azure").setLevel(logging.WARNING)


start_time_string = os.getenv("TEST_START_TIME")
stop_time_string = os.getenv("TEST_STOP_TIME")

test_start_time = datetime.strptime(start_time_string, "%Y-%m-%dT%H:%M:%SZ").astimezone(UTC)
test_stop_time = datetime.strptime(stop_time_string, "%Y-%m-%dT%H:%M:%SZ").astimezone(UTC)

print(f"test_start_time  : {test_start_time}")
print(f"test_end_time    : {test_stop_time}")


metric_check_time = test_stop_time - timedelta(seconds=40)  # detecting the end of the test can take 30s, add 10s buffer

query_processor = QueryProcessor(
    workspace_id=log_analytics_workspace_id,
    token_credential=DefaultAzureCredential(),
    tenant_id=tenant_id,
    subscription_id=subscription_id,
    resource_group_name=resource_group_name,
    workspace_name=log_analytics_workspace_name,
)

print(f"metric_check_time: {metric_check_time}")
check_results_query = """
AppMetrics
| where AppRoleName == "aoai-api-simulator" // only check the metrics for the simulated API
| summarize max(TimeGenerated)
"""

query_processor.wait_for_greater_than_or_equal(check_results_query, metric_check_time)

timespan = (datetime.now(UTC) - timedelta(days=1), datetime.now(UTC))


####################################################################
# Ensure the base latency is low
#


def validate_request_latency(table: Table):
    mean_latency = table.rows[0][0]
    if mean_latency > 10:
        return f"Mean latency is too high: {mean_latency}"
    return None


query_processor.add_query(
    title="Base Latency",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-simulator.latency.base"
| summarize Sum=sum(Sum),  Count = sum(ItemCount), Max=max(Max)
| project mean_latency_ms=1000*Sum/Count, max_latency_ms=1000*Max
""".strip(),
    timespan=timespan,
    show_query=True,
    include_link=True,
    validation_func=validate_request_latency,
)


####################################################################
# Show the number of completion tokens per request
#

query_processor.add_query(
    title="Completion tokens per request",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-simulator.tokens.used"
    | extend token_type = tostring(Properties["token_type"])
| where token_type == "completion"
| summarize Sum=sum(Sum),  Count = sum(ItemCount)
| project avg_tokens_per_request=Sum/Count
""".strip(),
    timespan=timespan,
    show_query=True,
    include_link=True,
)


####################################################################
# Show the RPS over the test
#

query_processor.add_query(
    title="RPS over time",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-simulator.latency.base"
| summarize RPS = sum(ItemCount)/10 by bin(TimeGenerated, 10s)
| project TimeGenerated, RPS
""".strip(),
    is_chart=True,
    columns=["RPS"],
    chart_config={
        "height": 15,
        "min": 0,
        "colors": [
            asciichart.yellow,
        ],
    },
    timespan=timespan,
    show_query=True,
    include_link=True,
)


####################################################################
# Show the base latency over the test
#


query_processor.add_query(
    title="Latency (base) over time in ms (mean - yellow, max - blue)",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-simulator.latency.base"
| summarize Sum=sum(Sum),  Count = sum(ItemCount), Max=max(Max) by bin(TimeGenerated, 10s)
| project TimeGenerated, mean_latency_ms=1000*Sum/Count, max_latency_ms=1000*Max
| render timechart
""".strip(),
    is_chart=True,
    columns=["mean_latency_ms", "max_latency_ms"],
    chart_config={
        "height": 15,
        "min": 0,
        "colors": [
            asciichart.yellow,
            asciichart.blue,
        ],
    },
    timespan=timespan,
    show_query=True,
    include_link=True,
)


query_errors = query_processor.run_queries()

if query_errors:
    exit(1)
