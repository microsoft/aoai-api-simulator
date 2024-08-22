#!/bin/bash
set -e

#
# NOTE: This is a helper script, not intended to be run directly
# This script is used to post load test processing
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

function show_usage() {
  echo
  echo "run-load-test-post-steps.sh"
  echo
  echo "Run post steps for load test"
  echo
  echo -e "\t--filename\t(Required)The filename for the post load test steps"
  echo -e "\t--test-start-time\t(Required)The time the load test started"
  echo -e "\t--test-stop-time\t(Required)The time the load test finished"
  echo
}

# Set default values here
test_start_time=""
test_stop_time=""
filename=""


# Process switches:
while [[ $# -gt 0 ]]
do
  case "$1" in
    --filename)
      filename=$2
      shift 2
      ;;
    --test-start-time)
      test_start_time=$2
      shift 2
      ;;
    --test-stop-time)
      test_stop_time=$2
      shift 2
      ;;
    *)
      echo "Unexpected '$1'"
      show_usage
      exit 1
      ;;
  esac
done


if [[ -z $filename ]]; then
  echo "--filename must be specified"
  show_usage
  exit 1
fi
if [[ -z $test_start_time ]]; then
  echo "--test-start-time must be specified"
  show_usage
  exit 1
fi
if [[ -z $test_stop_time ]]; then
  echo "--test-stop-time must be specified"
  show_usage
  exit 1
fi


#
# Load env var and output values
#

if [[ -f "$script_dir/../.env" ]]; then
	echo "Loading .env"
	source "$script_dir/../.env"
fi

if [[ ! -f "$script_dir/../infra/output.json" ]]; then
  echo "output.json not found - have you deployed the base infra?"
  exit 1
fi
rg_name=$(jq -r .rgName < "$script_dir/../infra/output.json")
if [[ -z "$rg_name" ]]; then
  echo "Resource Group Name (rgName) not found in output.json"
  exit 1
fi

log_analytics_workspace_name=$(jq -r '.logAnalyticsName // ""'< "$script_dir/../infra/output.json")
if [[ -z "${log_analytics_workspace_name}" ]]; then
	echo "Log Analytics Workspace Name not found in output.json"
	exit 1
fi

log_analytics_workspace_id=$(az monitor log-analytics workspace show --resource-group "$rg_name" --name "$log_analytics_workspace_name" --query "customerId" --output tsv)
if [[ -z "${log_analytics_workspace_id}" ]]; then
	echo "Error getting log analytics workspace id"
	exit 1
fi


subscription_id=$(az account show --output tsv --query id)
tenant_id=$(az account show --output tsv --query tenantId)



TEST_START_TIME="$test_start_time" \
TEST_STOP_TIME="$test_stop_time" \
LOG_ANALYTICS_WORKSPACE_ID="$log_analytics_workspace_id" \
LOG_ANALYTICS_WORKSPACE_NAME="$log_analytics_workspace_name" \
TENANT_ID="$tenant_id" \
SUBSCRIPTION_ID="$subscription_id" \
RESOURCE_GROUP_NAME="$rg_name" \
 python "$filename" 
