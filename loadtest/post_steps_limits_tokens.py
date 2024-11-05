import logging
import os
from datetime import UTC, datetime, timedelta

import asciichartpy as asciichart
from azure.identity import DefaultAzureCredential
from common.config import (
    log_analytics_workspace_id,
    log_analytics_workspace_name,
    resource_group_name,
    subscription_id,
    tenant_id,
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

time_vars = f"let startTime = datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')});\nlet endTime = datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')});"


####################################################################
# Ensure the base latency remains low with rate-limiting in place
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
    and Name == "aoai-api-simulator.latency.base"
| summarize Sum=sum(Sum),  Count = sum(ItemCount), Max=max(Max)
| project mean_latency_ms=1000*Sum/Count, max_latency_ms=1000*Max
""".strip(),
    timespan=timespan,
    show_query=True,
    include_link=True,
    validation_func=validate_request_latency,
)


####################################################################
# Ensure the rate-limiting allows the expected tokens per 10s period
#


def validate_mean_tokens_used_per_minute(table: Table):
    # Check if the mean TPM is within the expected range
    # The deployment for the tests has 100,000 Tokens Per Minute (TPM) limit
    mean_tokens_per_minute = int(table.rows[0][0])
    low_value = 95_000
    high_value = 105_000
    if mean_tokens_per_minute > high_value:
        return f"Mean tokens per minute is too high: {mean_tokens_per_minute} (expected between {low_value} and {high_value})"
    if mean_tokens_per_minute < low_value:
        return f"Mean tokens per minute is too low: {mean_tokens_per_minute} (expected between {low_value} and {high_value})"
    return None


query_processor.add_query(
    title="Mean Rate-Limiting Tokens Per Minute",
    query=f"""
let interval = 60s;
{time_vars}
let timeRange = range TimeStamp from startTime to endTime step interval
| summarize count() by bin(TimeStamp, interval) | project TimeStamp; // align values to interval boundaries
let query = AppMetrics
| where TimeGenerated >= startTime
    and TimeGenerated <= endTime
    and Name == "aoai-api-simulator.tokens.rate-limit"
| extend deployment = tostring(Properties["deployment"])
| summarize Sum=sum(Sum),  Count = sum(ItemCount), Max=max(Max) by bin(TimeGenerated, interval);
let aggregateQuery =timeRange
| join kind=leftouter query on $left.TimeStamp == $right.TimeGenerated
| project TimeGenerated=TimeStamp, Sum=coalesce(Sum, 0.0), Count=coalesce(Count, 0), Max=coalesce(Max,0.0)
| summarize total_token_count = sum(Sum) by bin(TimeGenerated, interval);
let row_count = toscalar (aggregateQuery | count);
aggregateQuery
| order by TimeGenerated desc | take row_count - 1 // TODO - skip first result (potentially incomplete minute)
| order by TimeGenerated asc | take row_count - 2 // TODO - skip last result (potentially incomplete minute)
| summarize avg_tokens_per_minute = avg(total_token_count)
""".strip(),
    timespan=timespan,
    show_query=True,
    include_link=True,
    validation_func=validate_mean_tokens_used_per_minute,
)


query_processor.add_query(
    title="Mean Consumption Tokens Per 10s (successful requests, billed tokens)",
    query=f"""
let interval = 60s;
{time_vars}
let timeRange = range TimeStamp from startTime to endTime step interval
| summarize count() by bin(TimeStamp, interval) | project TimeStamp; // align values to interval boundaries
let query = AppMetrics
| where TimeGenerated >= startTime
    and TimeGenerated <= endTime
    and Name == "aoai-api-simulator.tokens.used"
| extend deployment = tostring(Properties["deployment"]), token_type=tostring(Properties["token_type"])
| where token_type == "completion"| summarize Sum=sum(Sum),  Count = sum(ItemCount), Max=max(Max) by bin(TimeGenerated, interval);
let aggregateQuery =timeRange
| join kind=leftouter query on $left.TimeStamp == $right.TimeGenerated
| project TimeGenerated=TimeStamp, Sum=coalesce(Sum, 0.0), Count=coalesce(Count, 0), Max=coalesce(Max,0.0)
| summarize total_token_count = sum(Sum) by bin(TimeGenerated, interval);
let row_count = toscalar (aggregateQuery | count);
aggregateQuery
| order by TimeGenerated desc | take row_count - 1 // TODO - skip first result (potentially incomplete minute)
| order by TimeGenerated asc | take row_count - 2 // TODO - skip last result (potentially incomplete minute)
| summarize avg_tokens_per_minute = avg(total_token_count)
""".strip(),
    timespan=timespan,
    show_query=True,
    include_link=True,
    validation_func=validate_mean_tokens_used_per_minute,
)


####################################################################
# Ensure that we _do_ get 429 responses as expected
#


def validate_429_count(table: Table):
    # With the level of user load targetting the deployment, we expect a high number of 429 responses
    number_of_429_responses = table.rows[0][0]
    if number_of_429_responses < 100:
        return f"The number of 429 responses is too low: {number_of_429_responses}"
    return None


query_processor.add_query(
    title="Number of 429 responses (should be high)",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-api-simulator.latency.base"
| extend status_code = Properties["status_code"]
| where status_code == 429
| summarize ItemCount=sum(ItemCount)
""".strip(),
    timespan=timespan,
    show_query=True,
    include_link=True,
    validation_func=validate_429_count,
)


####################################################################
# Show the RPS over time
#

query_processor.add_query(
    title="Tokens per 10s over time (Used - yellow, Requested - blue)",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and (Name == "aoai-api-simulator.tokens.used" or Name == "aoai-api-simulator.tokens.requested")
| extend deployment = tostring(Properties["deployment"])
| summarize total_token_count = sum(Sum) by bin(TimeGenerated, 10s), Name
| evaluate pivot(Name, sum(total_token_count))
| render timechart with (title="Tokens per 10s over time")
""".strip(),
    is_chart=True,
    columns=["aoai-api-simulator.tokens.used", "aoai-api-simulator.tokens.requested"],
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


####################################################################
# Show the RPS over time
#

query_processor.add_query(
    title="Latency (base) over time in ms (mean - yellow, max - blue)",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-api-simulator.latency.base"
| summarize Sum=sum(Sum),  Count = sum(ItemCount), Max=max(Max) by bin(TimeGenerated, 10s)
| project TimeGenerated, mean_latency_ms=1000*Sum/Count, max_latency_ms=1000*Max
| render timechart with (title="Latency (base) over time in ms")
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


query_errors = query_processor.run_queries(
    all_queries_link_text="Show all queries in Log Analytics",
)

if query_errors:
    exit(1)
