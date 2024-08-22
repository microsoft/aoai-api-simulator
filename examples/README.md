# Examples

This folder contains a number of examples of how to extend the behaviour of the API simulator:

| Path                                | Description                                                                                                                                                                                |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `openai_deployment_config.json`     | An example configuration file for controlling the simulated model deployments (e.g. rate-limits)                                                                                           |
| `forwarder_doc_intelligence`                  | An example of providing a custom request forwarder to enable forwarding (and recording) responses for a document intelligence endpoint. It also shows how to create a multi-file extension |
| `generator_echo`                  | A minimal generator extension that adds an endpoint that echoes back request content                                                                                                       |
| `generator_replace_chat_completion` | An example of how to replace a built-in generator with a modified version                                                                                                                  |
