from aoai_api_simulator.record_replay.models import hash_body


def test_multipart_hash():
    # Ensure that we get the same hash for the same body, ignoring the boundary value
    hash1 = hash_body(
        {"content-type": "multipart/form-data; boundary=some-boundary-value"},
        b"""--some-boundary-value
Content-Disposition: form-data; name="response_format"

json
--some-boundary-value
Content-Disposition: form-data; name="file"; filename="short-spanish.mp3"
Content-Type: audio/mpeg

qwerty
--some-boundary-value--""",
    )

    hash2 = hash_body(
        {"content-type": "multipart/form-data; boundary=another-boundary-value"},
        b"""--another-boundary-value
Content-Disposition: form-data; name="response_format"

json
--another-boundary-value
Content-Disposition: form-data; name="file"; filename="short-spanish.mp3"
Content-Type: audio/mpeg

qwerty
--another-boundary-value--""",
    )

    assert hash1 == hash2, "expect hash to be the same for the same body, ignoring the boundary value"
