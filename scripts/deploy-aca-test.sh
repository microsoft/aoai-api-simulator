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

api_fqdn=$(jq -r .apiSimFqdn < "$script_dir/../infra/output.json")
if [[ -z "$api_fqdn" ]]; then
  echo "API endpoint (apiSimFqdn) not found in output.json"
  exit 1
fi

echo "=="
echo "== Testing API is up and running at https://$api_fqdn"
echo "=="

curl -s --max-time 30 -w "\nGot response: %{http_code}" "https://$api_fqdn/" || echo -e "\nTimed out"

echo -e "\n\n"
