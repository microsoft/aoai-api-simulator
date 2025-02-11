#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Get the directory of the Helm chart
HELM_CHART_DIR="$script_dir/../../helm/aoaisim"
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

# Copy OPENAI_DEPLOYMENT_CONFIG_PATH to Helm Chart
if [[ ${#OPENAI_DEPLOYMENT_CONFIG_PATH} -eq 0 ]]; then
  echo 'ERROR: Missing environment variable OPENAI_DEPLOYMENT_CONFIG_PATH' 1>&2
  exit 6
fi

cp "$OPENAI_DEPLOYMENT_CONFIG_PATH" "$HELM_CHART_DIR/.openai_deployment_config.json"

USER_ID=$(az ad signed-in-user show --output tsv --query id)
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
    "simulatorApiKey": {
      "value": "${SIMULATOR_API_KEY}"
    },
    "azureOpenAIKey": {
      "value": "${AZURE_OPENAI_KEY}"
    },
    "agentVMSize": {
      "value": "${AGENT_VM_SIZE}"
    },
    "currentUserPrincipalId": {
      "value": "${USER_ID}"
    }
  }
}
EOF

DEPLOYMENT_NAME="deployment-${BASENAME}-${LOCATION}-main"
cd "$script_dir/../"
echo "=="
echo "==Starting main bicep deployment ($DEPLOYMENT_NAME)"
echo "=="
output=$(az deployment group create \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --template-file aks-infra.bicep \
  --name "$DEPLOYMENT_NAME" \
  --parameters "$script_dir/azuredeploy.parameters.json" \
  --output json)
echo "$output" | jq "[.properties.outputs | to_entries | .[] | {key:.key, value: .value.value}] | from_entries" > "$script_dir/../../output.json"
echo -e "\n"

# Get AKS credentials
echo "Getting AKS credentials..."

AKS_CLUSTER_NAME=$(jq -r .aksClusterName < "$script_dir/../../output.json")
if [[ -z "$AKS_CLUSTER_NAME" ]]; then
  echo "AKS Cluster Name not found in output.json"
  exit 1
fi
az aks get-credentials --resource-group $RESOURCE_GROUP_NAME --name $AKS_CLUSTER_NAME --overwrite-existing

# Deploy the simulator
echo "Deploying the simulator..."

ACR_LOGIN_SERVER=$(jq -r .containerRegistryLoginServer < "$script_dir/../../output.json")
if [[ -z "$ACR_LOGIN_SERVER" ]]; then
  echo "Container registry login server not found in output.json"
  exit 1
fi
IMAGE_REPO="${ACR_LOGIN_SERVER}/aoai-api-simulator"
IMAGE_TAG=${SIMULATOR_IMAGE_TAG:-latest}

KEYVAULT_NAME=$(jq -r .keyVaultName < "$script_dir/../../output.json")
if [[ -z "$KEYVAULT_NAME" ]]; then
  echo "Key vault name not found in output.json"
  exit 1
fi

KUBELET_CLIENT_ID=$(jq -r .kubeletClientId < "$script_dir/../../output.json")
if [[ -z "$KUBELET_CLIENT_ID" ]]; then
  echo "Kubelet Client ID not found in output.json"
  exit 1
fi

TENANT_ID=$(az account show --query tenantId -o tsv)

STORAGE_ACCOUNT_NAME=$(jq -r .storageAccountName < "$script_dir/../../output.json")
if [[ -z "$STORAGE_ACCOUNT_NAME" ]]; then
  echo "Storage Account Name not found in output.json"
  exit 1
fi

STORAGE_ACCOUNT_KEY=$(az storage account keys list --account-name $STORAGE_ACCOUNT_NAME --resource-group $RESOURCE_GROUP_NAME --query "[0].value" -o tsv)
FILE_SHARE_NAME="simulator"

helm upgrade --install aoaisim "$HELM_CHART_DIR" \
    --set image.repository=$IMAGE_REPO \
    --set image.tag=$IMAGE_TAG \
    \
    --set config.simulatorMode=$SIMULATOR_MODE \
    --set config.recordingDir=$RECORDING_DIR \
    --set config.recordingAutoSave=$RECORDING_AUTO_SAVE \
    --set config.extensionPath=$EXTENSION_PATH \
    --set config.azureOpenAIEndpoint=$AZURE_OPENAI_ENDPOINT \
    --set config.logLevel=$LOG_LEVEL \
    \
    --set keyVault.name=$KEYVAULT_NAME \
    --set keyVault.tenantId=$TENANT_ID \
    --set keyVault.clientId=$KUBELET_CLIENT_ID \
    \
    --set azureFiles.resourceGroup=$RESOURCE_GROUP_NAME \
    --set azureFiles.azureStorageAccountName=$STORAGE_ACCOUNT_NAME \
    --set azureFiles.azureStorageAccountKey=$STORAGE_ACCOUNT_KEY \
    --set azureFiles.fileShareName=$FILE_SHARE_NAME