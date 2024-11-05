# Changelog

## vNext

- add notes here for the next release
- Add support for translation endpoint i.e. whisper models. ([#59](https://github.com/microsoft/aoai-api-simulator/pull/59) [@wtulloch](https://github.com/wtulloch))
  - This also includes internal changes to support non-token based rate limiting
- Add support for specifying the `dimension` parameter in in embeddings requests for `text-embedding-3` and later models ([#55](https://github.com/microsoft/aoai-api-simulator/pull/55) - [@tanya-borisova](https://github.com/tanya-borisova))
- Ensure that an API key is always generated if not provided ([#56](https://github.com/microsoft/aoai-api-simulator/pull/56) - [@lucashuet93](https://github.com/lucashuet93))
- **BREAKING CHANGE** Requests for an incompatible model (e.g. chat requests for an embedding model) fail with a 400 error ([#58](https://github.com/microsoft/aoai-api-simulator/pull/58) - [@tanya-borisova](https://github.com/tanya-borisova))
- Terraform deployment option ([#60](https://github.com/microsoft/aoai-api-simulator/pull/60) [@mluker](https://github.com/mluker))
- Support for ARM architecture for local Docker builds ([#32](https://github.com/microsoft/aoai-api-simulator/pull/32) [@mluker](https://github.com/mluker))
- <!-- markdownlint-disable line-length -->
- Numerous fixes and repo improvements: [#24](https://github.com/microsoft/aoai-api-simulator/pull/24), [#26](https://github.com/microsoft/aoai-api-simulator/pull/26), [#38](https://github.com/microsoft/aoai-api-simulator/pull/38), [#41](https://github.com/microsoft/aoai-api-simulator/pull/41), [#42](https://github.com/microsoft/aoai-api-simulator/pull/42), [#43](https://github.com/microsoft/aoai-api-simulator/pull/43), [#45](https://github.com/microsoft/aoai-api-simulator/pull/45), [#51](https://github.com/microsoft/aoai-api-simulator/pull/51) [@martinpeck](https://github.com/martinpeck)
- <!-- markdownlint-enable line-length -->

## v0.5 - 2024-08-27

- Migrate to [current repo](https://github.com/microsoft/aoai-api-simulator/) from [previous repo](https://github.com/stuartleeks/aoai-simulated-api)
  - **BREAKING CHANGE:**: rename `aoai-simulated-api` to `aoai-api-simulator` in code (also for `aoai_simulated_api` package)
  - **BREAKING CHANGE:**: update metric prefix from `aoai-simulated-api.` to `aoai-api-simulator.`
- Return to sliding window rate limiting. This change moves from the limits package to a custom rate-limiting implementation to address performance with sliding windows ([#51](https://github.com/stuartleeks/aoai-simulated-api/pull/51))
- Update rate-limit handling for tokens based on experimentation (limited set of models currently - see [#52](https://github.com/stuartleeks/aoai-simulated-api/issues/52))

## v0.4 - 2024-06-25

- Extensibility updates
  - Focus core simulator on OpenAI (moved doc intelligence generator to example extension)
  - API authorization is now part of forwarders/generators to allow extensions to add their own authentication schemes. **BREAKING CHANGE:** If you have custom forwarders/generators they need to be updated to handle this (see examples for implementation details)
  - Enable adding custom rate limiters
  - Move latency calculation to generators. This allows for extensions to customise latency values. NOTE: If you have custom generators they need to be updated to handle this (see examples for implementation details)
- Add rate-limiting for replayed requests
- Add `ALLOW_UNDEFINED_OPENAI_DEPLOYMENTS` configuration option to control whether the simulator will generate responses for any deployment or only known deployments
- Fix: tokens used by streaming completions were not included in token counts for rate-limits
- Token usage metrics are now split into prompt and completion tokens using metric dimensions
- **BREAKING CHANGE:** Token metrics have been renamed from `aoai-simulator.tokens_used` and `aoai-simulator.tokens_requested` to `aoai-simulator.tokens.used` and `aoai-simulator.tokens.requested` for consistency with latency metric names
- Dimension size for embedding deployments can now be specified in config ([#39](https://github.com/stuartleeks/aoai-simulated-api/pull/39) - [@MDUYN](https://github.com/MDUYN))

## v0.3 - 2024-05-03

- Improve error info when no matching handler is found
- Fix tokens-per-minute to requests-per-minute conversion bug

## v0.2 - 2024-04-24

- Add option to configure latency for generated responses for OpenAI endpoints
- Add `/++/config` endpoint to get and set configuration values

## v0.1 - 2024-04-22

Initial tagged version

Includes

- Update Dockerfile to enable building with pre-cached tiktoken file (enables running without internet access) ([#23](https://github.com/stuartleeks/aoai-simulated-api/pull/23) [@aerjenn](https://github.com/aerjenn))
- Document Intelligence example ([#2](https://github.com/stuartleeks/aoai-simulated-api/pull/2) [@mcollier](https://github.com/mcollier))
