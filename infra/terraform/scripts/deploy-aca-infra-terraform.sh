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

RESOURCE_GROUP_NAME="aoaisim"

cat << EOF > "$script_dir/../tf.tfvars"
azure_subscription_id = "$(az account show --query id --output tsv)"
resource_group_name   = "${RESOURCE_GROUP_NAME}"
location            = "${LOCATION}"
base_name            = "${BASENAME}"
simulator_mode       = "${SIMULATOR_MODE}"
simulator_api_key     = "${SIMULATOR_API_KEY}"
recording_dir        = "${RECORDING_DIR}"
recording_auto_save   = "${RECORDING_AUTO_SAVE}"
extension_path       = "${EXTENSION_PATH}"
azure_openai_endpoint = "${AZURE_OPENAI_ENDPOINT}"
azure_openai_key      = "${AZURE_OPENAI_KEY}"
log_level            = "${LOG_LEVEL}"
simulator_image_tag   = "${image_tag}"
current_user_principal_id = "${user_id}"
EOF

cd "$script_dir/../"
echo "=="
echo "==Starting teraform deployment"
echo "=="

terraform init
terraform apply -auto-approve -var-file="$script_dir/../tf.tfvars"
terraform output -json | jq 'with_entries(.value |= .value)' > "$script_dir/../../output.json"
echo -e "\n"
