#################################################################################
# context.values keys
# These are keys for 'well-known' values stored in the context.values dictionary.

# SIMULATOR_KEY_OPERATION_NAME stores the name of the OpenAI operation performed (e.g. embeddings, completion)
SIMULATOR_KEY_OPERATION_NAME = "Operation-Name"

# SIMULATOR_KEY_DEPLOYMENT_NAME stores the name of the OpenAI deployment used
SIMULATOR_KEY_DEPLOYMENT_NAME = "Deployment-Name"

# SIMULATOR_KEY_LIMITER stores the name of the limiter used for the request
# For built-in generators/forwarders this is 'openai'),
# but this allows additional limiters to be added via extensions
SIMULATOR_KEY_LIMITER = "Limiter"

# SIMULATOR_KEY_OPENAI_PROMPT_TOKENS stores the number of tokens used for the prompt
SIMULATOR_KEY_OPENAI_PROMPT_TOKENS = "X-OpenAI-Tokens-Prompt"

# SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS stores the number of tokens used for the completion (i.e. generated tokens)
SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS = "X-OpenAI-Tokens-Completion"

# SIMULATOR_KEY_OPENAI_TOTAL_TOKENS stores the total number of tokens used in the request
SIMULATOR_KEY_OPENAI_TOTAL_TOKENS = "X-OpenAI-Tokens-Total"

# SIMULATOR_KEY_OPENAI_RATE_LIMIT_TOKENS stores the number of tokens used for rate limiting
SIMULATOR_KEY_OPENAI_RATE_LIMIT_TOKENS = "X-OpenAI-Tokens-Rate-Limit"

# SIMULATOR_KEY_OPENAI_MAX_TOKENS_REQUESTED stores the max_tokens from the request
SIMULATOR_KEY_OPENAI_MAX_TOKENS_REQUESTED = "X-OpenAI-Max-Tokens-Requested"

# SIMULATOR_KEY_OPENAI_MAX_TOKENS_EFFECTIVE stores the effective max_tokens value for the request
# (taking into account the model's limits/defaults)
SIMULATOR_KEY_OPENAI_MAX_TOKENS_EFFECTIVE = "X-OpenAI-Max-Tokens-Effective"

# SIMULATOR_KEY_OPENAI_REQUEST_FILE_SIZE stores the size of the request file in bytes
SIMULATOR_KEY_OPENAI_REQUEST_FILE_SIZE_BYTES = "X-OpenAI-Request-File-Size"


# TARGET_DURATION_MS stores the target duration of the request in milliseconds
# For recorded requests this will be the recorded duration
# For generated requests this will be estimated based on the request type and response length
TARGET_DURATION_MS = "Simulator-Target-Duration"


# LIMTER_OPENAI_TOKENS is the name of the limiter used for OpenAI requests
# that are rate-limited using tokens (and requests-per-10-seconds)
LIMITER_OPENAI_TOKENS = "openai-tokens"

# LIMITER_OPENAI_REQUESTS is the name of the limiter used for OpenAI requests
# that are rate-limited using requests-per-minute
LIMITER_OPENAI_REQUESTS = "openai-requests"


OPENAI_OPERATION_EMBEDDINGS = "embeddings"
OPENAI_OPERATION_COMPLETIONS = "completions"
OPENAI_OPERATION_CHAT_COMPLETIONS = "chat_completions"
OPENAI_OPERATION_TRANSLATION = "translation"
