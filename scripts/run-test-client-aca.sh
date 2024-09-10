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


echo "== Running test-client against simulator at https://$api_fqdn"
cd tools/test-client
TEST_OPENAI_KEY="${SIMULATOR_API_KEY}" TEST_OPENAI_ENDPOINT="https://$api_fqdn" TEST_FORM_RECOGNIZER_ENDPOINT="https://$api_fqdn" python app.py
