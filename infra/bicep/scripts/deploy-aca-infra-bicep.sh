#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [[ -f "$script_dir/../../../.env" ]]; then
	echo "Loading .env"
	source "$script_dir/../../../.env"
fi

if [[ ${#BASENAME} -eq 0 ]]; then
  echo 'ERROR: Missing environment variable BASENAME' 1>&2
  exit 6
fi

if [[ ${#LOCATION} -eq 0 ]]; then
  echo 'ERROR: Missing environment variable LOCATION' 1>&2
  exit 6
fi

if [[ ${#SIMULATOR_MODE} -eq 0 ]]; then
  echo 'ERROR: Missing environment variable SIMULATOR_MODE' 1>&2
  exit 6
fi


if [[ ${#RECORDING_DIR} -eq 0 ]]; then
  echo 'Defaulting to /mnt/simulator/recording for RECORDING_DIR' 1>&2
  RECORDING_DIR="/mnt/simulator/recording"
fi

# Deployment uses .openai_deployment_config.json as the config
# So copy OPENAI_DEPLOYMENT_CONFIG_PATH to .openai_deployment_config.json
if [[ ${#OPENAI_DEPLOYMENT_CONFIG_PATH} -eq 0 ]]; then
  echo 'ERROR: Missing environment variable OPENAI_DEPLOYMENT_CONFIG_PATH' 1>&2
  exit 6
fi

cp "$OPENAI_DEPLOYMENT_CONFIG_PATH" "$script_dir/../../.openai_deployment_config.json"

image_tag=${SIMULATOR_IMAGE_TAG:-latest}

user_id=$(az ad signed-in-user show --output tsv --query id)

RESOURCE_GROUP_NAME=${RESOURCE_GROUP_NAME:-aoaisim}

cat << EOF > "$script_dir/azuredeploy.parameters.json"
{
  "\$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "location": {
      "value": "${LOCATION}"
    },
    "baseName": {
      "value": "${BASENAME}"
    },
	"simulatorMode": {
	  "value": "${SIMULATOR_MODE}"
	},
	"simulatorApiKey": {
	  "value": "${SIMULATOR_API_KEY}"
	},
	"recordingDir": {
	  "value": "${RECORDING_DIR}"
	},
	"recordingAutoSave": {
	  "value": "${RECORDING_AUTO_SAVE}"
	},
	"extensionPath": {
	  "value": "${EXTENSION_PATH}"
	},
	"azureOpenAIEndpoint": {
	  "value": "${AZURE_OPENAI_ENDPOINT}"
	},
	"azureOpenAIKey": {
	  "value": "${AZURE_OPENAI_KEY}"
	},
	"logLevel": {
	  "value": "${LOG_LEVEL}"
	},
	"simulatorImageTag": {
	  "value": "${image_tag}"
	},
	"currentUserPrincipalId": {
	  "value": "${user_id}"
	}
  }
}
EOF

deployment_name="deployment-${BASENAME}-${LOCATION}"
cd "$script_dir/../"
echo "=="
echo "==Starting main bicep deployment ($deployment_name)"
echo "=="
output=$(az deployment group create \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --template-file main.bicep \
  --name "$deployment_name" \
  --parameters "$script_dir/azuredeploy.parameters.json" \
  --output json)
echo "$output" | jq "[.properties.outputs | to_entries | .[] | {key:.key, value: .value.value}] | from_entries" > "$script_dir/../../output.json"
echo -e "\n"
