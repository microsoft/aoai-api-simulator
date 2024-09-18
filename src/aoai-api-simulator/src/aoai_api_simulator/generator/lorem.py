import logging
import random
import time

from aoai_api_simulator.generator.openai_tokens import (
    num_tokens_from_string,
)

logger = logging.getLogger(__name__)


def get_lorem_factor(max_tokens: int):
    # Use a sliding factor for the number of words to generate based on the max_tokens
    if max_tokens > 500:
        return 0.72
    if max_tokens > 100:
        return 0.6
    return 0.5


# pylint: disable-next=too-few-public-methods
class LoremReference:
    """
    Generating large amounts of lorem text can be slow, so we pre-generate a set of reference values.
    These are then combined to generate the required amount of text for API requests
    """

    model_name: str
    values: dict[int, list[str]]
    token_sizes: list[int]

    def __init__(self, model_name: str, reference_values: dict[int, list[str]]):
        self.model_name = model_name
        self.values = reference_values
        self.token_sizes = sorted(reference_values.keys(), reverse=True)

    def get_value_for_size(self, size: int) -> tuple[str, int] | None:
        for token_size in self.token_sizes:
            if token_size <= size:
                values = self.values[token_size]
                value = random.choice(values)
                return (value, token_size)
        return None


lorem_reference_values: dict[str, LoremReference] = {}


def generate_lorem_reference_text_values(token_values: list[int], model_name: str):
    value_count = 5  # number of reference values of each size to generate
    values = {}
    for max_tokens in token_values:
        generated_texts = [raw_generate_lorem_text(max_tokens, model_name) for _ in range(value_count)]
        values[max_tokens] = generated_texts

    return LoremReference(model_name, values)


def generate_lorem_text(max_tokens: int, model_name: str):
    text = ""
    target = max_tokens

    if model_name not in lorem_reference_values:
        logger.info("Generating lorem reference values for model %s...", model_name)
        start_time = time.perf_counter()
        token_sizes = [2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 4000]
        lorem_reference_values[model_name] = generate_lorem_reference_text_values(token_sizes, model_name)
        duration = time.perf_counter() - start_time
        logger.info("Generated lorem reference values for model %s (took %ss)", model_name, duration)
    reference_values = lorem_reference_values[model_name]

    separator = ""
    while target > 0:
        value = reference_values.get_value_for_size(target)
        if value is None:
            break
        new_text, size = value
        text += separator + new_text
        separator = " "
        target -= size

    while num_tokens_from_string(text, model_name) > max_tokens:
        # remove last word
        last_space = text.rfind(" ")
        text = text[:last_space]

    return text


lorem_words = [
    "ullamco",
    "labore",
    "cupidatat",
    "ipsum",
    "elit,",
    "esse",
    "officia",
    "aliquip",
    "do",
    "magna",
    "duis",
    "consequat",
    "exercitation",
    "occaecat",
    "ea",
    "laboris",
    "sit",
    "reprehenderit",
    "velit",
    "dolor",
    "enim",
    "irure",
    "anim",
    "nisi",
    "amet,",
    "culpa",
    "commodo",
    "consectetur",
    "eiusmod",
    "minim",
    "mollit",
    "fugiat",
    "cillum",
    "non",
    "deserunt",
    "veniam,",
    "est",
    "eu",
    "qui",
    "tempor",
    "adipiscing",
    "aliqua",
    "et",
    "nostrud",
    "ex",
    "incididunt",
    "aute",
    "nulla",
    "in",
    "proident,",
    "sunt",
    "id",
    "lorem",
    "pariatur",
    "excepteur",
    "ut",
    "ad",
    "sed",
    "sint",
    "laborum",
    "voluptate",
    "dolore",
    "quis",
]


def raw_lorem_get_word(count: int = 1) -> str:
    return " ".join([random.choice(lorem_words) for _ in range(count)])


def raw_generate_lorem_text(max_tokens: int, model_name: str) -> str:
    # The simplest approach to generating the compltion would
    # be to add a word at a time and count the tokens until we reach the limit
    # For large max_token values that will be slow, so we
    # estimate the number of words to generate based on the max_tokens
    # and then measure the number of tokens in that text
    # Then we repeat for the remaining token count
    # (allowing for some degree of error as tokens don't exactly combine that way )
    target = max_tokens
    full_text = ""
    sep = ""
    while target > 5:
        factor = get_lorem_factor(target)
        init_word_count = int(factor * target)
        # text = lorem.get_word(count=init_word_count)
        text = raw_lorem_get_word(count=init_word_count)
        used = num_tokens_from_string(text, model_name)
        if used > target:
            break
        full_text += sep + text
        sep = " "
        target -= used
        target -= 2  # allow for space and error margin in token count addition

    # Now top up the text to the max_tokens
    # by adding a word at a time
    while True:
        new_text = full_text + " " + raw_lorem_get_word()  # lorem.get_word()
        if num_tokens_from_string(new_text, model_name) > max_tokens:
            break
        full_text = new_text

    return full_text
