#!/bin/bash
set -e

#
# Runs a load test with 1s latency and no limits
# Used to validate the added latency of the simulator under load.
#
# The script runs a load test in Container Apps 
# and then runs follow-up steps to validate the results.
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

endpoint=${ENDPOINT:=chat}
if [[ "$endpoint"  == "translation" ]]; then
  test_file=./loadtest_translations_1s_latency.py
  latency_min=900
  latency_max=1100
  # Use an undefined deployment, i.e no limiting applied
  deployment_name="whisper-no-limit"
  user_count=50
else
  test_file=./loadtest_chat_completions_1s_latency.py
  latency_min=900
  latency_max=1100
  # Use an undefined deployment, i.e no limiting applied
  deployment_name="gpt-35-turbo-no-limit"
  user_count=100
fi

echo "Using test file: $test_file"
echo ""



set +e
result=$(\
  LOCUST_USERS=$user_count \
  LOCUST_RUN_TIME=3m \
  LOCUST_SPAWN_RATE=1 \
  TEST_FILE=$test_file \
  DEPLOYMENT_NAME=$deployment_name \
  ALLOW_429_RESPONSES=true \
  ./scripts/_run-load-test-aca.sh)
run_exit_code=$?
set -e

echo -e "________________\n$result"

if [[ "$run_exit_code" != "0" ]]; then
  echo "Error running load test - exiting"

  echo "$result"
  exit 1
fi


test_start_time=$(echo "$result" | jq -r '.start_time')
test_stop_time=$(echo "$result" | jq -r '.end_time')

echo "--test-start-time: '$test_start_time'"
echo "--test-stop-time: '$test_stop_time'"
echo ""
echo "Running post steps"

LATENCY_MAX=$latency_max LATENCY_MIN=$latency_min "$script_dir/_run-load-test-post-steps.sh" \
  --test-start-time "$test_start_time" \
  --test-stop-time "$test_stop_time" \
  --filename ./loadtest/post_steps_added_latency.py
