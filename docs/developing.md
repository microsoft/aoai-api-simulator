# Contributing to the Azure OpenAI API Simulator

This file contains notes for anyone contributing and developing the Azure OpenAI API Simulator.

The simplest way to work with and develop the simulator code is within a [Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers) in VS Code.

The repo contains Dev Container configuration that will sets up a container and install all of the dependencies needed to develop the simulator.

The rest of this document assumes that you are working within a Dev Container, though many of the instructions will work outside of a container too.

## Repo Contents

The top level repo is structured as follows:
```
.
├── docs            # Markdown documentation (such as this file)
├── examples        # contains examples of how the similator might be used
├── infra           # contains the bicep files to deploy the simulator to Azure Container Apps
├── loadtest        # locust-based load tests for validating the simulator performance
├── scripts         # scripts to help with development/deployment (mostly bash scripts, called from `Makefile`)
├── src             # the Azure OpenAI API Simulator code
├── tests           # tests for the Azure OpenAI API Simulator
└── tools           # test client and other tools
```
The `src` directory contains the main code for the simulator.

## The Makefile

Almost all of the common tasks for running or testing the simulator are available via the `Makefile`.

The following section of this document describes some of the more commonly used rules:

Make command                     | Description
---------------------------------|-----------------------------------------
`make help`                      | Show the help message with a full set of available rules
`make install-requirements`      | Installs the PyPI requirements
`make run-simulated-api`         | Launches the AOAI Simulated API locally
`make test`                      | Run the suite of PyTest tests (in verbose mode)
`make lint`                      | Lints the aoai-api-simulator source code
`make deploy-aca`                | Runs the deployment scripts for Azure Container Apps

For a full set of rules, type `make help` from the command line and you will be presented with a list of available rules.

## Creating Pull Requests against the Azure OpenAI API Simulator
    
When creating a pull request, please ensure that you have run the linter and tests locally before pushing your changes.

To run the linter run `make lint`. Ensure that you are not adding additional linting issues.

To run the tests run `make test`. Make sure that the test suite runs successfully.

## Creating a Release of the Azure OpenAI API Simulator

### Pre-release checklist

Before creating a new release, please ensure you have run through the following steps:

- Ensure that the tests run successfully
- Compare the linter output to the last release, and ensure that no additional linting issues have been created - this helps to avoid accumulating a build-up of linting issues
- Deploy the simulator to Container Apps
- Run load tests against the deployed simulator (see [Load tests](#load-tests))

### Load Tests

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
