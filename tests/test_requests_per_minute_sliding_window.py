import math
import time

from aoai_api_simulator.limiters import RequestsPerMinuteSlidingWindow


def add_success_request(
    window: RequestsPerMinuteSlidingWindow,
    timestamp: float,
    expected_remaining_requests=None,
    msg: str = None,
):
    result = window.add_request(timestamp=timestamp)
    assert result.success, msg
    assert result.retry_reason is None
    assert result.retry_after is None
    if expected_remaining_requests is not None:
        assert result.remaining_requests == expected_remaining_requests
    return result


def test_allow_first_request_within_limits():
    window = RequestsPerMinuteSlidingWindow(requests_per_minute=60)

    add_success_request(window, timestamp=1, expected_remaining_requests=59)


def test_allow_request_in_new_window_period():
    window = RequestsPerMinuteSlidingWindow(requests_per_minute=10)

    add_success_request(window, timestamp=1, expected_remaining_requests=9)
    add_success_request(window, timestamp=2, expected_remaining_requests=8)
    add_success_request(window, timestamp=3, expected_remaining_requests=7)
    add_success_request(window, timestamp=4, expected_remaining_requests=6)
    add_success_request(window, timestamp=5, expected_remaining_requests=5)
    add_success_request(window, timestamp=6, expected_remaining_requests=4)
    add_success_request(window, timestamp=7, expected_remaining_requests=3)
    add_success_request(window, timestamp=8, expected_remaining_requests=2)
    add_success_request(window, timestamp=9, expected_remaining_requests=1)
    add_success_request(window, timestamp=10, expected_remaining_requests=0)

    # The requests above are all in the initial 60s period
    # Make another request at 61s, which should also be allowed as the time window has moved on
    # so the first request no longer counts in the requests_per_minute window
    add_success_request(window, timestamp=61, expected_remaining_requests=0)


def test_block_when_too_many_requests():
    window = RequestsPerMinuteSlidingWindow(requests_per_minute=10)

    add_success_request(window, timestamp=2)
    add_success_request(window, timestamp=3)
    add_success_request(window, timestamp=3)
    add_success_request(window, timestamp=3)
    add_success_request(window, timestamp=3)
    add_success_request(window, timestamp=3)
    add_success_request(window, timestamp=3)
    add_success_request(window, timestamp=3)
    add_success_request(window, timestamp=3)
    add_success_request(window, timestamp=4)

    # The requests above used all the requests in the 10s period
    result = window.add_request(timestamp=5)
    assert not result.success
    assert result.retry_reason == "requests"
    assert result.retry_after == 57


def test_perf_successful_requests():
    simulated_rpm = 1_000_000

    window = RequestsPerMinuteSlidingWindow(requests_per_minute=simulated_rpm)

    start = time.perf_counter()

    number_of_requests = math.ceil(simulated_rpm * 2)  # simulate 2 minutes of requests
    for i in range(number_of_requests):
        window.add_request(timestamp=i)

    duration = time.perf_counter() - start
    avg_duration = duration / number_of_requests
    assert avg_duration < 0.000_1


def test_perf_blocked_requests():
    simulated_rpm = 1_000_000
    window = RequestsPerMinuteSlidingWindow(requests_per_minute=1000)  # RPM is lo

    start = time.perf_counter()

    number_of_requests = math.ceil(simulated_rpm * 2)  # simulate 2 minutes of requests
    for i in range(number_of_requests):
        window.add_request(timestamp=i)

    duration = time.perf_counter() - start
    avg_duration = duration / number_of_requests
    assert avg_duration < 0.000_1


def test_1000_request_limit():
    # Test the sliding window with a large number of requests
    window = RequestsPerMinuteSlidingWindow(requests_per_minute=1000)

    start_timestamp = time.time()
    timestamp = start_timestamp

    for _ in range(1000):
        result = add_success_request(window, timestamp=timestamp)
        timestamp += 0.00001

    assert result.remaining_requests == 0

    # Check that we now are rate-limited
    result = window.add_request(timestamp=timestamp)
    assert not result.success
    assert result.retry_reason == "requests"
    assert result.retry_after >= 59

    # Check that we're rate-limited for 10s
    for _ in range(100):
        result = window.add_request(timestamp=timestamp)
        timestamp += 0.00001
        assert not result.success

    # Check that we can send requests again after 60s
    add_success_request(window, timestamp=start_timestamp + 60)
