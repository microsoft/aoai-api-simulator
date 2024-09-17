import logging
from typing import Tuple

import tiktoken

logger = logging.getLogger(__name__)

# For details on the token counting, see https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken


warnings = {}


def _warn_once(warning_key: str, message: str):
    if warning_key not in warnings:
        logger.warning(message)
        warnings[warning_key] = True


def get_max_completion_tokens(request_body, model_name: str, prompt_tokens: int) -> Tuple[int | None, int]:
    """
    Returns a tuple of the requested max tokens and the actual max tokens to use.
    """
    requested_max_tokens = request_body.get("max_tokens")

    # Based on https://platform.openai.com/docs/guides/text-generation/managing-tokens
    default_max_tokens = 128000 if model_name == "gpt-4o" else 4097

    upper_limit = default_max_tokens - prompt_tokens

    if requested_max_tokens is None:
        max_tokens = upper_limit
    else:
        max_tokens = min(requested_max_tokens, upper_limit)

    return requested_max_tokens, max_tokens


def num_tokens_from_string(string: str, model: str) -> int:
    """Returns the number of tokens in a text string."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        _warn_once(model, f"Warning: model ({model}) not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(string))
    return num_tokens


def num_tokens_from_messages(messages, model):
    """Return the number of tokens used by a list of messages."""
    # pylint: disable-next=global-statement
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        _warn_once(model, f"Warning: model ({model}) not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        _warn_once(
            model, "Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613."
        )
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        _warn_once(model, "Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    elif "whisper" in model:
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301")
    else:
        raise NotImplementedError(
            f"num_tokens_from_messages() is not implemented for model {model}. "
            + "See https://github.com/openai/openai-python/blob/main/chatml.md for information "
            + " on how messages are converted to tokens."
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens
