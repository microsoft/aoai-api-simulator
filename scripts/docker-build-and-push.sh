#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
echo "script_dir1: $script_dir"
if [[ -f "$script_dir/../.env" ]]; then
	echo "Loading .env"
	source "$script_dir/../.env"
fi

if [[ ! -f "$script_dir/../infra/output.json" ]]; then
  echo "output.json not found - have you deployed the base infra?"
  exit 1
fi

image_tag=${SIMULATOR_IMAGE_TAG:-latest}

acr_login_server=$(jq -r .containerRegistryLoginServer < "$script_dir/../infra/output.json")
if [[ -z "$acr_login_server" ]]; then
  echo "Container registry login server not found in output.json"
  exit 1
fi
acr_login_server=$(jq -r .containerRegistryLoginServer < "$script_dir/../infra/output.json")
acr_name=$(jq -r .containerRegistryName < "$script_dir/../infra/output.json")
if [[ -z "$acr_name" ]]; then
  echo "Container registry name not found in output.json"
  exit 1
fi

echo "=="
echo "== Building and pushing aoai-api-simulator image (tag: $image_tag) to $acr_login_server"
echo "=="

src_path=$(realpath "$script_dir/../src/aoai-api-simulator")

docker build --platform linux/amd64 -t "${acr_login_server}/aoai-api-simulator:$image_tag" "$src_path" -f "$src_path/Dockerfile"

az acr login --name "$acr_name"
docker push "${acr_login_server}/aoai-api-simulator:$image_tag"

echo -e "\n"
