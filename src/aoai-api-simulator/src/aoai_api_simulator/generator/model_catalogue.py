from aoai_api_simulator.models import OpenAIChatModel, OpenAIEmbeddingModel, OpenAIWhisperModel

# models: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models

model_catalogue = {
    "gpt-3.5-turbo": OpenAIChatModel(name="gpt-3.5-turbo", supports_json_schema=False),
    "gpt-3.5-turbo-0613": OpenAIChatModel(name="gpt-3.5-turbo-0613", supports_json_schema=False),
    "gpt-4": OpenAIChatModel(name="gpt-4", supports_json_schema=True),
    "gpt-4o": OpenAIChatModel(name="gpt-4o", supports_json_schema=True),
    "text-embedding-ada-001": OpenAIEmbeddingModel(name="text-embedding-ada-001", supports_custom_dimensions=False),
    "text-embedding-ada-002": OpenAIEmbeddingModel(name="text-embedding-ada-002", supports_custom_dimensions=False),
    "text-embedding-3-small": OpenAIEmbeddingModel(name="text-embedding-3-small", supports_custom_dimensions=True),
    "text-embedding-3-medium": OpenAIEmbeddingModel(name="text-embedding-3-medium", supports_custom_dimensions=True),
    "text-embedding-3-large": OpenAIEmbeddingModel(name="text-embedding-3-large", supports_custom_dimensions=True),
    "text-embedding-3-xlarge": OpenAIEmbeddingModel(name="text-embedding-3-xlarge", supports_custom_dimensions=True),
    "whisper": OpenAIWhisperModel(name="whisper"),
}

DEFAULT_CHAT_MODEL = "gpt-3.5-turbo"
DEFAULT_EMBEDDING_MODEL = "text-embedding-ada-002"
DEFAULT_WHISPER_MODEL = "whisper"
