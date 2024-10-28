import math
import time

import pytest
from aoai_api_simulator.limiters import TokensPerMinuteSlidingWindow


def add_success_request(
    window: TokensPerMinuteSlidingWindow,
    token_count: int,
    timestamp: float,
    expected_remaining_requests=None,
    expected_remaining_tokens=None,
    msg: str = None,
):
    result = window.add_request(token_cost=token_count, timestamp=timestamp)
    assert result.success, msg
    assert result.retry_reason is None
    assert result.retry_after is None
    if expected_remaining_requests is not None:
        assert result.remaining_requests == expected_remaining_requests
    if expected_remaining_tokens is not None:
        assert result.remaining_tokens == expected_remaining_tokens
    return result


def test_allow_first_request_within_limits():
    window = TokensPerMinuteSlidingWindow(requests_per_10_seconds=10, tokens_per_minute=100)

    add_success_request(window, timestamp=1, token_count=5, expected_remaining_requests=9, expected_remaining_tokens=95)


def test_allow_request_in_new_window_period():
    window = TokensPerMinuteSlidingWindow(requests_per_10_seconds=10, tokens_per_minute=100)

    add_success_request(window, timestamp=1, token_count=5, expected_remaining_requests=9, expected_remaining_tokens=95)
    add_success_request(window, timestamp=2, token_count=5, expected_remaining_requests=8, expected_remaining_tokens=90)
    add_success_request(window, timestamp=3, token_count=5, expected_remaining_requests=7, expected_remaining_tokens=85)
    add_success_request(window, timestamp=4, token_count=5, expected_remaining_requests=6, expected_remaining_tokens=80)
    add_success_request(window, timestamp=5, token_count=5, expected_remaining_requests=5, expected_remaining_tokens=75)
    add_success_request(window, timestamp=6, token_count=5, expected_remaining_requests=4, expected_remaining_tokens=70)
    add_success_request(window, timestamp=7, token_count=5, expected_remaining_requests=3, expected_remaining_tokens=65)
    add_success_request(window, timestamp=8, token_count=5, expected_remaining_requests=2, expected_remaining_tokens=60)
    add_success_request(window, timestamp=9, token_count=5, expected_remaining_requests=1, expected_remaining_tokens=55)
    add_success_request(
        window, timestamp=10, token_count=5, expected_remaining_requests=0, expected_remaining_tokens=50
    )
    # The requests above are all in the initial 10s period
    # Make another request at 11s, which should also be allowed as the time window has moved on
    # so the first request no longer counts in the requests_per_10s window (but it's tokens still count in the 60s window)
    add_success_request(
        window, timestamp=11, token_count=5, expected_remaining_requests=0, expected_remaining_tokens=45
    )


def test_block_when_too_many_requests():
    window = TokensPerMinuteSlidingWindow(requests_per_10_seconds=10, tokens_per_minute=100)

    # Time:                 0    1     2     3    4     5    6    7     8     9   10    11   12
    # # Requests                       1     8    1
    # 10s request window:   0    0     1     9   10    10   10   10    10    10   10    10    9

    add_success_request(window, timestamp=2, token_count=5)
    add_success_request(window, timestamp=3, token_count=5)
    add_success_request(window, timestamp=3, token_count=5)
    add_success_request(window, timestamp=3, token_count=5)
    add_success_request(window, timestamp=3, token_count=5)
    add_success_request(window, timestamp=3, token_count=5)
    add_success_request(window, timestamp=3, token_count=5)
    add_success_request(window, timestamp=3, token_count=5)
    add_success_request(window, timestamp=3, token_count=5)
    add_success_request(window, timestamp=4, token_count=5)

    # The requests above used all the requests in the 10s period
    result = window.add_request(timestamp=5, token_cost=5)
    assert not result.success
    assert result.retry_reason == "requests"
    assert result.retry_after == 7


def test_block_when_too_many_tokens_exact():
    window = TokensPerMinuteSlidingWindow(requests_per_10_seconds=10, tokens_per_minute=100)

    add_success_request(window, timestamp=10, token_count=20)
    add_success_request(window, timestamp=20, token_count=20)
    add_success_request(window, timestamp=30, token_count=20)
    add_success_request(window, timestamp=40, token_count=40)

    # Time:               0    10    20     30     40     50     60    70     80     90
    # Tokens:                  20    20     20     40
    # 60s token window:   0    20    40     60    100    100    100    80     60

    # The requests above used all the tokens for the 60s period
    result = window.add_request(timestamp=50, token_cost=20)
    assert not result.success
    assert result.retry_reason == "tokens"
    # At t=70, the t=10 request will be out of the sliding window
    # leaving 80 tokens used in the window
    # We're testing at t=50, so retry_after should be 70 - 50 = 20
    assert result.retry_after == 20

    # Check the calculation of remaining tokens for a larger request
    result = window.add_request(timestamp=50, token_cost=40)
    assert not result.success
    assert result.retry_reason == "tokens"
    # at t=80, the t=10 and t=20 requests will be out of the sliding window
    # leaving 60 tokens used in the window
    assert result.retry_after == 30

    # Check the calculation of remaining tokens for a larger request
    result = window.add_request(timestamp=50, token_cost=100)
    assert not result.success
    assert result.retry_reason == "tokens"
    # at t=100, all requests will be out of the sliding window
    assert result.retry_after == 50


def test_block_when_too_many_tokens_overflow():
    window = TokensPerMinuteSlidingWindow(requests_per_10_seconds=10, tokens_per_minute=100)

    add_success_request(window, timestamp=10, token_count=24)
    add_success_request(window, timestamp=20, token_count=24)
    add_success_request(window, timestamp=30, token_count=24)
    add_success_request(window, timestamp=40, token_count=24)

    # Time:               0    10    20     30     40     50     60    70     80     90
    # Tokens:                  24    24     24     24
    # 60s token window:   0    24    48     72     96     96     96    72     48

    # The requests above used all the tokens for the 60s period
    result = window.add_request(timestamp=50, token_cost=20)
    assert not result.success
    assert result.retry_reason == "tokens"
    # At t=70, the t=10 request will be out of the sliding window
    # leaving 72 tokens used in the window
    # We're testing at t=50, so retry_after should be 70 - 50 = 20
    assert result.retry_after == 20

    # Check the calculation of remaining tokens for a larger request
    result = window.add_request(timestamp=50, token_cost=40)
    assert not result.success
    assert result.retry_reason == "tokens"
    # at t=80, the t=10 and t=20 requests will be out of the sliding window
    # leaving 48 tokens used in the window
    assert result.retry_after == 30

    # Check the calculation of remaining tokens for a larger request
    result = window.add_request(timestamp=50, token_cost=100)
    assert not result.success
    assert result.retry_reason == "tokens"
    # at t=100, all requests will be out of the sliding window
    assert result.retry_after == 50


def test_block_second_request():
    window = TokensPerMinuteSlidingWindow(requests_per_10_seconds=10, tokens_per_minute=100)

    add_success_request(window, timestamp=10, token_count=100)

    # Time:               0    10    20     30     40     50     60    70     80     90
    # Tokens:                 100
    # 60s token window:   0   100   100    100    100    100    100     0
    result = window.add_request(timestamp=20, token_cost=100)
    assert not result.success
    assert result.retry_reason == "tokens"
    assert result.retry_after == 50


@pytest.mark.slow
def test_perf_successful_requests_SLOW():
    simulated_tpm = 1_000_000
    requests_per_10_seconds = simulated_tpm * 60 / 1000

    window = TokensPerMinuteSlidingWindow(
        requests_per_10_seconds=requests_per_10_seconds, tokens_per_minute=simulated_tpm
    )

    start = time.perf_counter()

    number_of_requests = math.ceil(requests_per_10_seconds * 120)  # simulate 2 minutes of requests
    for i in range(number_of_requests):
        # keeping tokens low and distributing timestamps to avoid rate-limiting
        window.add_request(timestamp=i, token_cost=1)

    duration = time.perf_counter() - start
    avg_duration = duration / number_of_requests
    assert avg_duration < 0.000_1


@pytest.mark.slow
def test_perf_blocked_requests():
    simulated_tpm = 1_000_000
    requests_per_10_seconds = simulated_tpm * 60 / 1000

    window = TokensPerMinuteSlidingWindow(
        requests_per_10_seconds=requests_per_10_seconds, tokens_per_minute=simulated_tpm
    )

    start = time.perf_counter()

    number_of_requests = math.ceil(requests_per_10_seconds * 120)  # simulate 2 minutes of requests
    for i in range(number_of_requests):
        # set token cost high to trigger rate-limiting on most requests
        window.add_request(timestamp=i, token_cost=1_000_000)

    duration = time.perf_counter() - start
    avg_duration = duration / number_of_requests
    assert avg_duration < 0.000_1


def test_100k_token_limit():
    # Test the sliding window with a large number of requests
    window = TokensPerMinuteSlidingWindow(requests_per_10_seconds=100, tokens_per_minute=100_000)

    # simulate 10 RPS, with 200 tokens
    # should manage 100,000 / 200 = 500 requests successfully
    timestamp = time.time()

    # Send through 50s of requests (should succeed)
    for i in range(500):
        add_success_request(window, timestamp=timestamp, token_count=200)  # , msg=f"test_part_1:{i}")
        timestamp += 0.100001

    # Check that we now are rate-limited
    result = window.add_request(timestamp=timestamp, token_cost=200)
    assert not result.success
    assert result.retry_reason == "tokens"
    assert result.retry_after == 10  # we used all the tokens in 50s - resets in 10s

    # Check that we're rate-limited for 10s
    for _ in range(100):
        result = window.add_request(timestamp=timestamp, token_cost=200)
        timestamp += 0.100001
        assert not result.success

    # Check that we can send requests again after 10s
    add_success_request(window, timestamp=timestamp, token_count=200)
