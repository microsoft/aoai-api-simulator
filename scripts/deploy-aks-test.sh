#!/bin/bash
set -e

EXTERNAL_IP=$(kubectl get svc aoaisim --output jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo "=="
echo "== Testing API is up and running at http://$EXTERNAL_IP"
echo "=="

curl -s --max-time 30 -w "\nGot response: %{http_code}" "http://$EXTERNAL_IP/" || echo -e "\nTimed out"

echo -e "\n\n"
