# Changelog

## vNext

- Migrate to current repo
  - **BREAKING CHANGE:**: rename `aoai-simulated-api` to `aoai-api-simulator` in code (also for `aoai_simulated_api` package)
  - **BREAKING CHANGE:**: update metric prefix from `aoai-api-simulator.` to `aoai-api-simulator.`
- Return to sliding window rate limiting. This change moves from the limits package to a custom rate-limiting implementation to address performance with sliding windows (#20)
- Update rate-limit handling for tokens based on experimentation (limited set of models currently - see #52)

# v0.4 - 2024-06-25

- Extensibility updates
  - Focus core simulator on OpenAI (moved doc intelligence generator to example extension)
  - API authorization is now part of forwarders/generators to allow extensions to add their own authentication schemes. **BREAKING CHANGE:** If you have custom forwarders/generators they need to be updated to handle this (see examples for implementation details)
  - Enable adding custom rate limiters
  - Move latency calculation to generators. This allows for extensions to customise latency values. NOTE: If you have custom generators they need to be updated to handle this (see examples for implementation details)
- Add rate-limiting for replayed requests
- Add `ALLOW_UNDEFINED_OPENAI_DEPLOYMENTS ` configuration option to control whether the simulator will generate responses for any deployment or only known deployments
- Fix: tokens used by streaming completions were not included in token counts for rate-limits
- Token usage metrics are now split into prompt and completion tokens using metric dimensions
- **BREAKING CHANGE:** Token metrics have been renamed from `aoai-simulator.tokens_used` and `aoai-simulator.tokens_requested` to `aoai-simulator.tokens.used` and `aoai-simulator.tokens.requested` for consistency with latency metric names

## v0.3 - 2024-05-03

- Improve error info when no matching handler is found
- Fix tokens-per-minute to requests-per-minute conversion bug

## v0.2 - 2024-04-24

- Add option to configure latency for generated responses for OpenAI endpoints
- Add `/++/config` endpoint to get and set configuration values

## v0.1 - 2024-04-22

Initial tagged version