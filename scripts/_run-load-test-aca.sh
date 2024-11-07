#!/bin/bash
set -e

#
# NOTE: This is a helper script, not intended to be run directly
# This script is used to run a load test against the deployed API
# Progress output is written to stderr
# Result output is written to stdout
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# A function to output an error and exit with non-zero exit code
function error_exit {
  echo "$1" >&2
  jq -n --arg msg "$1" '{"result": "error", "message": $msg}'
  exit 1
}
function log {
  echo -e "$1" >&2
}

if [[ -f "$script_dir/../.env" ]]; then
	log "Loading .env"
	source "$script_dir/../.env"
fi



if [[ -z "$TEST_FILE" ]]; then
  error_exit "TEST_FILE not specified"
fi
if [[ ! -f "$script_dir/../loadtest/$TEST_FILE" ]]; then
  error_exit "Test file $TEST_FILE not found"
fi

LOCUST_USERS=${LOCUST_USERS:-20}
LOCUST_RUN_TIME=${LOCUST_RUN_TIME:-3m}
LOCUST_SPAWN_RATE=${LOCUST_SPAWN_RATE:-0.5}
MAX_TOKENS=${MAX_TOKENS:-100}
ALLOW_429_RESPONSES=${ALLOW_429_RESPONSES:-false}

if [[ -z "$DEPLOYMENT_NAME" ]]; then
  error_exit "DEPLOYMENT_NAME not specified"
fi

if [[ ! -f "$script_dir/../infra/output.json" ]]; then
  # call error_exit function
  error_exit "output.json not found - have you deployed the base infra?"
fi

job_name="load-test"

api_fqdn=$(jq -r .apiSimFqdn < "$script_dir/../infra/output.json")
if [[ -z "$api_fqdn" ]]; then
  error_exit "API endpoint (apiSimFqdn) not found in output.json"
fi

acr_login_server=$(jq -r .containerRegistryLoginServer < "$script_dir/../infra/output.json")
if [[ -z "$acr_login_server" ]]; then
  error_exit "Container registry login server not found in output.json"
fi
acr_name=$(jq -r .containerRegistryName < "$script_dir/../infra/output.json")
if [[ -z "$acr_name" ]]; then
  error_exit "Container registry name not found in output.json"
fi

aca_env_name=$(jq -r .acaEnvName < "$script_dir/../infra/output.json")
if [[ -z "$acr_name" ]]; then
  error_exit "Container App Environment name not found in output.json"
fi

rg_name=$(jq -r .rgName < "$script_dir/../infra/output.json")
if [[ -z "$rg_name" ]]; then
  error_exit "Resource Group Name (rgName) not found in output.json"
fi

aca_identity_id=$(jq -r .acaIdentityId < "$script_dir/../infra/output.json")
if [[ -z "$aca_identity_id" ]]; then
  error_exit "ACA Identity ID (acaIdentityId) not found in output.json"
fi


key_vault_name=$(jq -r '.keyVaultName // ""'< "$script_dir/../infra/output.json")
if [[ -z "${key_vault_name}" ]]; then
	echo "Key Vault Name not found in output.json"
	exit 1
fi
applicationinsights_connection_string=$(az keyvault secret show --vault-name "$key_vault_name" --name applicationinsights-connection-string --query value --output tsv)
if [[ -z "${applicationinsights_connection_string}" ]]; then
	echo "App Insights Connection String not found in Key Vault"
	exit 1
fi


log "=="
log "== Building and pushing aoai-api-simulator-load-test image to $acr_login_server"
log "=="

src_path=$(realpath "$script_dir/../loadtest")

cp -R "${script_dir}/../tests/audio" "${script_dir}/../loadtest/.audio"
docker build -t "${acr_login_server}/aoai-api-simulator-load-test:latest" "$src_path" -f "$src_path/Dockerfile" 1>&2

az acr login --name "$acr_name" 1>&2
docker push "${acr_login_server}/aoai-api-simulator-load-test:latest" 1>&2

log "\n"

log "=="
log "== Creating load test job"
log "=="

log "\n"

log "!!! API: $api_fqdn"
log "!!! Deployment: $DEPLOYMENT_NAME"

# https://learn.microsoft.com/en-us/azure/container-apps/jobs-get-started-cli?pivots=container-apps-job-manual
# https://docs.locust.io/en/stable/configuration.html#all-available-configuration-options
az containerapp job create \
  --name "$job_name" \
  --resource-group "$rg_name" \
  --environment "$aca_env_name" \
  --trigger-type "Manual" \
  --replica-retry-limit 1 \
  --replica-completion-count 1 \
  --parallelism 1 \
  --replica-timeout 1800 \
  --registry-server "$acr_login_server" \
  --registry-identity "$aca_identity_id" \
  --image "${acr_login_server}/aoai-api-simulator-load-test:latest" \
  --cpu "1" \
  --memory "2Gi" \
  --command "locust" \
  --env-vars "LOCUST_LOCUSTFILE=$TEST_FILE" "LOCUST_HOST=https://${api_fqdn}/" "LOCUST_USERS=$LOCUST_USERS" "LOCUST_SPAWN_RATE=$LOCUST_SPAWN_RATE" "LOCUST_AUTOSTART=true" "LOCUST_RUN_TIME=$LOCUST_RUN_TIME" "LOCUST_AUTOQUIT=10" "SIMULATOR_API_KEY=${SIMULATOR_API_KEY}" "APP_INSIGHTS_CONNECTION_STRING=${applicationinsights_connection_string}" "MAX_TOKENS=${MAX_TOKENS}" "DEPLOYMENT_NAME=${DEPLOYMENT_NAME}" ALLOW_429_RESPONSES=${ALLOW_429_RESPONSES} 1>&2


start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
job_execution_name=$(az containerapp job start \
  --name "$job_name" \
  --resource-group "$rg_name" --output tsv --query name)

log "Job created and started ($job_execution_name). Waiting for completion..."

while true; do
  job_status=$(az containerapp job execution show --resource-group "$rg_name" --name "$job_name" --job-execution-name "$job_execution_name" --query properties.status --output tsv)
  if [[ "$job_status" == "Succeeded" ]]; then
    log "Job Succeeded!"
    break
  fi
  if [[ "$job_status" == "Failed" ]]; then
    error_exit "Job failed"
  fi
  log "Job status: $job_status ..."
  sleep 30
done

end_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
log "End time: $end_time"


# Output success result with start + end times
jq -n --arg start_time "$start_time" --arg end_time "$end_time" '{"result": "success", "start_time": $start_time, "end_time": $end_time}'
