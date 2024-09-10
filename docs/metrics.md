# Azure OpenAI API Simulator Metrics

To help you understand how the API Simulator is performing, we provide a number of metrics that you can use to monitor the simulator.

- [Azure OpenAI API Simulator Metrics](#azure-openai-api-simulator-metrics)
  - [aoai-api-simulator.latency.base](#aoai-api-simulatorlatencybase)
  - [aoai-api-simulator.latency.full](#aoai-api-simulatorlatencyfull)
  - [aoai-api-simulator.tokens.used](#aoai-api-simulatortokensused)
  - [aoai-api-simulator.tokens.requested](#aoai-api-simulatortokensrequested)
  - [aoai-api-simulator.tokens.rate-limit](#aoai-api-simulatortokensrate-limit)
  - [aoai-api-simulator.limits](#aoai-api-simulatorlimits)

## aoai-api-simulator.latency.base

Units: `seconds`

The `aoai-api-simulator.latency.base` metric measures the base latency of the simulator. This is the time taken to process a request _excluding_ any added latency.

Dimensions:

- `deployment`: The name of the deployment the metric relates to.
- `status_code`: The HTTP status code of the response.

## aoai-api-simulator.latency.full

Units: `seconds`

The `aoai-api-simulator.latency.full` metric measures the full latency of the simulator. This is the time taken to process a request _including_ any added latency.

Dimensions:

- `deployment`: The name of the deployment the metric relates to.
- `status_code`: The HTTP status code of the response.

## aoai-api-simulator.tokens.used

Units: `tokens`

The `aoai-api-simulator.tokens.used` metric measures the number of tokens used by the simulator in producing successful responses.

Dimensions:

- `deployment`: The name of the deployment the metric relates to.
- `token_type`: The type of token, e.g. `prompt` or `completion`.

## aoai-api-simulator.tokens.requested

Units: `tokens`

The `aoai-api-simulator.tokens.requested` metric measures the number of tokens requested. This is the total requested load on the simulator, including requests that were rate-limited.

Dimensions:

- `deployment`: The name of the deployment the metric relates to.
- `token_type`: The type of token, e.g. `prompt` or `completion`.

## aoai-api-simulator.tokens.rate-limit

Units: `tokens`

The `aoai-api-simulator.tokens.rate-limit` metric measures the number of tokens counted by the simulator for rate-limiting. This is different to `aoai-api-simulator.tokens.used` which corresponding to the billing count for tokens.

Dimensions:

- `deployment`: The name of the deployment the metric relates to.

## aoai-api-simulator.limits

Units: `requests`

The `aoai-api-simulator.limits` metric measures the number of requests that were rate-limited by the simulator.

Dimensions:

- `deployment`: The name of the deployment the metric relates to.
- `limit_type`: The type of limit that was hit, e.g. `requests` or `tokens`.
