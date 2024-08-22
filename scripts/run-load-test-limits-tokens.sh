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

# Set max tokens high to trigger rate-limiting by tokens not request count
# Since there are 6 RPM per 1000 TPM a max_tokens of 1000/6 = 167 will trigger rate limiting
# Keeping the value near that threshold makes the validation more granular
max_tokens=200

# Use deployment with 100k TPM limit
# 100k tokens per minute 
deployment_name="gpt-35-turbo-100k-token"




result=$(\
  LOCUST_USERS=30 \
  LOCUST_RUN_TIME=3m \
  LOCUST_SPAWN_RATE=2 \
  TEST_FILE=./test_chat_completions_no_added_latency.py \
  DEPLOYMENT_NAME=$deployment_name \
  MAX_TOKENS=$max_tokens \
  ALLOW_429_RESPONSES=true \
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
  --filename ./loadtest/post_steps_limits_tokens.py
