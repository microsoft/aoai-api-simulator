import requests

from .config import api_key


def set_simulator_completions_latency(endpoint: str, mean: float, std_dev: float):
    """
    Set the latency for the simulator completions endpoint

    :param endpoint: The simulator endpoint to set the latency for
    :param latency: The latency to set - specified in milliseconds per completion token
    """

    if endpoint.endswith("/"):
        endpoint = endpoint.strip("/")
    url = f"{endpoint}/++/config"
    response = requests.patch(
        url=url,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={"latency": {"open_ai_completions": {"mean": mean, "std_dev": std_dev}}},
        timeout=10,
    )
    response.raise_for_status()


def set_simulator_chat_completions_latency(endpoint: str, mean: float, std_dev: float):
    """
    Set the latency for the simulator completions endpoint

    :param endpoint: The simulator endpoint to set the latency for
    :param latency: The latency to set - specified in milliseconds per chat completion token
    """

    if endpoint.endswith("/"):
        endpoint = endpoint.strip("/")
    url = f"{endpoint}/++/config"
    response = requests.patch(
        url=url,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={"latency": {"open_ai_chat_completions": {"mean": mean, "std_dev": std_dev}}},
        timeout=10,
    )
    response.raise_for_status()
