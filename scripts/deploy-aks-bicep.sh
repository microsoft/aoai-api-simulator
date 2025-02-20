#!/bin/bash
set -e

#
# Main script for coordinating of the simulator to Azure Kubernetes Service (AKS)
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Get the directory of the IaC scripts
scripts_iac_dir="$script_dir/../infra/bicep/scripts"

# Deploy base resources (e.g. container registry)
"$scripts_iac_dir/deploy-base-bicep.sh"

# Build and push Docker image to container registry
"$script_dir/docker-build-and-push.sh"

# Deploy AKS etc
"$scripts_iac_dir/deploy-aks-infra-bicep.sh"

# Test that the deployment is functioning
"$script_dir/deploy-aks-test.sh"