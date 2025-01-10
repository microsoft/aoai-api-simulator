#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [[ -f "$script_dir/../../../.env" ]]; then
	echo "Loading .env"
	source "$script_dir/../../../.env"
fi

# Function to display help message
show_help() {
    echo "Usage: $0 [-h] [-g RESOURCE_GROUP] [-n AKS_NAME] [-r REGISTRY]"
    echo
    echo "   -h                    Display this help message"
    echo "   -g RESOURCE_GROUP     Resource group name"
    echo "   -n AKS_NAME           AKS name"
    echo "   -r REGISTRY           Registry to use for the simulator image"
}

# Default values
RESOURCE_GROUP_NAME=""
AKS_NAME=""

# Parse command line arguments
while getopts "hg:n:r:" opt; do
    case ${opt} in
        h )
            show_help
            exit 0
            ;;
        g )
            RESOURCE_GROUP_NAME=$OPTARG
            ;;
        n )
            AKS_NAME=$OPTARG
            ;;
        r )
            REGISTRY=$OPTARG
            ;;
        \? )
            echo "Invalid option: -$OPTARG" >&2
            show_help
            exit 1
            ;;
        : )
            echo "Option -$OPTARG requires an argument." >&2
            show_help
            exit 1
            ;;
    esac
done
shift $((OPTIND -1))

if [ -z "$RESOURCE_GROUP_NAME" ]; then
    echo "RESOURCE_GROUP_NAME is required."
    show_help
    exit 1
fi

if [ -z "$AKS_NAME" ]; then
    echo "AKS_NAME is required."
    show_help
    exit 1
fi

if [ -z "$REGISTRY" ]; then
    echo "REGISTRY is required."
    show_help
    exit 1
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

# Get AKS credentials
echo "Getting AKS credentials..."
az aks get-credentials --resource-group $RESOURCE_GROUP_NAME --name $AKS_NAME --overwrite-existing

# Deploy the simulator
echo "Deploying the simulator..."
IMAGE_REPO="${REGISTRY}/aoai-api-simulator"
IMAGE_TAG=${SIMULATOR_IMAGE_TAG:-latest}
helm upgrade --install aoaisim "$script_dir/../aoaisim" \
    --set image.repository=$IMAGE_REPO \
    --set image.tag=$IMAGE_TAG \
    --set config.simulatorMode=$SIMULATOR_MODE \
    --set config.recordingDir=$RECORDING_DIR \
    --set config.recordingAutoSave=$RECORDING_AUTO_SAVE \
    --set config.extensionPath=$EXTENSION_PATH \
    --set config.azureOpenAIEndpoint=$AZURE_OPENAI_ENDPOINT \
    --set config.logLevel=$LOG_LEVEL \

