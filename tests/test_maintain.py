from datetime import datetime
import time


fake_jwt = "1.2.3"


def test_create_presigned_url_log_with_timestamp(client):
    # create a log with a timestamp
    guid = "dg.hello/abc"
    request_data = {
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "timestamp": int(time.time()),
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
        "protocol": "s3",
        "additional_data": {"test_key": "test_val"},
    }
    res = client.post("/log/presigned_url", json=request_data)
    assert res.status_code == 201, res.text

    # the POST endpoint does not return data since it's async, so query
    res = client.get(
        "/log/presigned_url", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 200, res.text
    response_data = res.json()
    assert response_data.get("data"), response_data
    response_data = response_data["data"][0]
    request_timestamp = str(datetime.fromtimestamp(request_data.pop("timestamp")))
    response_timestamp = response_data.pop("timestamp").replace("T", " ")
    assert response_timestamp == request_timestamp

    # Avoid comparing auto-incremented id
    del response_data["id"]

    assert response_data == request_data


def test_create_presigned_url_log_with_bad_timestamp(client):
    # create a log with a timestamp
    guid = "dg.hello/abc"
    request_data = {
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "timestamp": 999999999999999,
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
        "protocol": "s3",
    }
    res = client.post("/log/presigned_url", json=request_data)
    assert res.status_code == 400, res.text


def test_create_presigned_url_log_without_timestamp(client):
    # create a log without a timestamp (should default to "now")
    guid = "dg.hello/abc"
    request_data = {
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
        "protocol": "s3",
        "additional_data": {"test_key": "test_val"},
    }
    res = client.post("/log/presigned_url", json=request_data)
    assert res.status_code == 201, res.text

    # the POST endpoint does not return data since it's async, so query
    res = client.get(
        "/log/presigned_url", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 200, res.text
    response_data = res.json()
    assert response_data.get("data"), response_data
    response_data = response_data["data"][0]
    del response_data["id"]  # auto-incremented id
    assert sorted(list(response_data.keys())) == sorted(
        list(request_data.keys()) + ["timestamp"]
    )
    now_timestamp = str(datetime.now()).split(" ")[0]
    response_timestamp = response_data.pop("timestamp").split("T")[0]
    assert response_timestamp == now_timestamp
    assert response_data == request_data


def test_create_presigned_url_log_wrong_body(client):
    guid = "dg.hello/abc"

    # create a log with missing fields
    request_data = {
        "status_code": 200,
        "sub": 10,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
    }
    res = client.post("/log/presigned_url", json=request_data)
    assert res.status_code == 422, res.text

    # create a log with unknown action
    request_data = {
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "not-an-action",
    }
    res = client.post("/log/presigned_url", json=request_data)
    assert res.status_code == 400, res.text

    # create a log with invalid 'additional_data'
    request_data = {
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
        "additional_data": "not-a-dict",
    }
    res = client.post("/log/presigned_url", json=request_data)
    assert res.status_code == 422, res.text

    # create a log with extra fields - should ignore the extra
    # fields and succeed
    request_data = {
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
        "extra_field": "hello",
    }
    res = client.post("/log/presigned_url", json=request_data)
    assert res.status_code == 201, res.text


def test_create_wrong_category(client):
    request_data = {
        "request_url": "/whatisthis",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
    }
    res = client.post("/log/whatisthis", json=request_data)
    assert res.status_code == 405, res.text
