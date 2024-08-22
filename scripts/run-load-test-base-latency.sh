#!/bin/bash
set -e

#
# Runs a load test with no added latency and no limits
# Used to validate the base latency of the simulator under load.
#
# The script runs a load test in Container Apps 
# and then runs follow-up steps to validate the results.
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Use an undefined deployment, i.e no limiting applied
deployment_name="gpt-35-turbo-no-limit"

result=$(\
  LOCUST_USERS=100 \
  LOCUST_RUN_TIME=5m \
  LOCUST_SPAWN_RATE=1 \
  TEST_FILE=./test_chat_completions_no_added_latency.py \
  DEPLOYMENT_NAME=$deployment_name \
  ./scripts/_run-load-test-aca.sh)

echo -e "________________\n$result"


test_start_time=$(echo "$result" | jq -r '.start_time')
test_stop_time=$(echo "$result" | jq -r '.end_time')

echo "--test-start-time: '$test_start_time'"
echo "--test-stop-time: '$test_stop_time'"
echo ""
echo "Running post steps"

"$script_dir/_run-load-test-post-steps.sh" \
  --test-start-time "$test_start_time" \
  --test-stop-time "$test_stop_time" \
  --filename ./loadtest/post_steps_base_latency.py
