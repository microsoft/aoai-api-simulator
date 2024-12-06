#!/bin/bash
set -e

#
# Main script for coordinating of the simulator to Azure Container Apps (ACA)
#

# Default value for deployment_target
deployment_target="aca"

# Parse input arguments
while getopts "t:" opt; do
  case $opt in
    t)
      deployment_target=$OPTARG
      ;;
    *)
      echo "Usage: $0 [-t deployment_target]"
      exit 1
      ;;
  esac
done

if [[ "$deployment_target" != "aca" && "$deployment_target" != "aks" ]]; then
  echo "Invalid deployment_target: $deployment_target"
  echo "Valid options are: aca or aks"
  exit 1
fi

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Get the directory of the IaC scripts
scripts_iac_dir="$script_dir/../infra/bicep/scripts"

# Deploy base resources (e.g. container registry)
"$scripts_iac_dir/deploy-base-bicep.sh"

# Build and push Docker image to container registry
"$script_dir/docker-build-and-push.sh"

# Deploy ACA etc
"$scripts_iac_dir/deploy-infra-bicep.sh"  -t "$deployment_target"

# est that the deployment is functioning
"$script_dir/deploy-aca-test.sh"

# show logs
"$script_dir/deploy-aca-show-logs.sh"
