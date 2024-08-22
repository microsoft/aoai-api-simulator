#!/bin/bash
set -e

#
# Main script for coordinating of the simulator to Azure Container Apps (ACA)
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"



if [[ -f "$script_dir/../.env" ]]; then
	echo "Loading .env"
	source "$script_dir/../.env"
fi


if [[ ! -f "$script_dir/../infra/output.json" ]]; then
  echo "output.json not found - have you deployed the base infra?"
  exit 1
fi

storage_account_name=$(jq -r .storageAccountName)
if [[ -z "$storage_account_name" ]]; then
  echo "Storage account name (storageAccountName) not found in output.json"
  exit 1
fi

file_share_name=$(jq -r .fileShareName < "$script_dir/../infra/output.json")
if [[ -z "$file_share_name" ]]; then
  echo "File share name (fileShareName) not found in output.json"
  exit 1
fi


storage_key=$(az storage account keys list --account-name "$storage_account_name" -o tsv --query '[0].value')

az storage file upload-batch --destination "$file_share_name" --source "$script_dir/../examples" --account-name "$storage_account_name" --account-key "$storage_key"