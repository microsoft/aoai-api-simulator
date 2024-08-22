#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [[ -f "$script_dir/../.env" ]]; then
	echo "Loading .env"
	source "$script_dir/../.env"
fi


if [[ ! -f "$script_dir/../infra/output.json" ]]; then
  echo "output.json not found - have you deployed the base infra?"
  exit 1
fi

rgName=$(jq -r .rgName < "$script_dir/../infra/output.json")
if [[ -z "$rgName" ]]; then
  echo "Resource Group Name (rgName) not found in output.json"
  exit 1
fi
acaName=$(jq -r .acaName < "$script_dir/../infra/output.json")
if [[ -z "$acaName" ]]; then
  echo "Container App Name (acaName) not found in output.json"
  exit 1
fi

echo "Running: az containerapp logs show --resource-group $rgName --name $acaName --format text"
az containerapp logs show --resource-group "$rgName" --name "$acaName" --format text

echo -e "\n"
