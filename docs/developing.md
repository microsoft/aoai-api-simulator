# Developing the API Simulator

This file contains some notes about developing the API simulator.

The simplest way to work with the simulator code is with [Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers) in VS Code.
The repo contains a Dev Container configuration that sets up a container with all the dependencies needed to develop the simulator.

## Repo Contents

- `infra` contains the bicep files to deploy the simulator to Azure Container Apps
- `src` contains the simulator code and tests
- `scripts` contains scripts to help with development/deployment
- `test-aoai.http` contains a collection of HTTP requests that can be run in VS Code using the REST Client extension

Under the `src` folder ther are the following subfolders:
- `aoai_api_simulator` - the simulator code
- `examples` - example code showing how to extend the simulator
- `loadtest` - locust-based load tests for validating the simulator performance
- `test-client` -  a simple client that can be used to test the simulator interactively
- `test-client-web` -  a simple web client that can be used to demo the chat completions
- `tests` - integration tests for validating the simulator

## Running the linter/tests

There is a `Makefile` in the root of the repo that contains some useful commands.

To run the linter run `make lint`.

To run the tests run `make test`.

## Pre-release checklist

- Ensure that the tests run
- Compare the linter output to the last release - this helps to avoid accumulating a build-up of linting issues
- Deploy the simulator to Container Apps
- Run load tests against the deployed simulator (see [Load tests](#load-tests))

### Load tests

The following load tests should be run against the simulator before a release:

#### Load test: Base latency (no added latency, no limits)

To run this test, run `./scripts/run-load-test-base-latency.sh`.

The test sends requests to the simulator as fast as possible with no latency and no rate limiting.
This test is useful for validating the base latency and understanding the maximum throughput of the simulator.


#### Load test: Added latency (1s latency, no limits)

To run this test, run `./scripts/run-load-test-added-latency.sh`.

The test sends requests to the simulator as fast as possible with 1s latency and no rate limiting.
This test is useful for validating the simulated latency behavior.

#### Load test: Rate limiting (no added latency, 10 requests per second)

To run this test, run `./scripts/run-load-test-limits-requests.sh`.

The simulator endpoint used in this test is configured for 100,000 tokens per minute.
This equates to 600 requests per minute or 10 requests per second.

This test uses 30 test users (i.e. ~30RPS) with a `max_tokens` value of 10 for each request.
By keeping the `max_tokens` value low, we should trigger the request-based rate limiting rather than the token-based limiting.


#### Load test: Token limiting (no added latency, 100,000 tokens per minute)

To run this test, run `./scripts/run-load-test-limits-tokens.sh`.

The simulator endpoint used in this test is configured for 100,000 tokens per minute.
This equates to ~16,667 tokens per 10 second window.

This test uses 30 test users (i.e. ~30RPS) with a `max_tokens` value of 200 for each request.
By keeping the `max_tokens` value high, we should trigger the token-based rate limiting rather than the request-based limiting.

> NOTE: Every 1000 tokens per minute allows 6 requests per minute. Provided the `max_tokens` value used is greater than 1000/6 = 167, the rate-limiting should be triggered by tokens rather than requests.
