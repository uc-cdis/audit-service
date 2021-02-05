from datetime import datetime
import pytest  # TODO remove once unused


def timestamp_for_date(date_string):
    dt = datetime.strptime(date_string, "%Y/%m/%d")
    return datetime.timestamp(dt)


PRESIGNED_URL_TEST_DATA = {
    "A1_1": {
        "username": "userA",
        "guid": "guid1",
        "timestamp": timestamp_for_date("2020/01/15"),
    },
    "A1_2": {
        "username": "userA",
        "guid": "guid1",
        "timestamp": timestamp_for_date("2020/10/31"),
    },
    "A2": {
        "username": "userA",
        "guid": "guid2",
        "timestamp": timestamp_for_date("2020/02/02"),
    },
    "A3": {
        "username": "userA",
        "guid": "guid3",
        "timestamp": timestamp_for_date("2020/03/04"),
    },
    "B1": {
        "username": "userB",
        "guid": "guid1",
        "timestamp": timestamp_for_date("2020/01/16"),
    },
}

fake_jwt = "1.2.3"


def submit_test_data(client):
    for test_data in PRESIGNED_URL_TEST_DATA.values():
        guid = "dg.hello/abc"
        request_data = {
            "request_url": f"/request_data/download/{guid}",
            "status_code": 200,
            "username": "audit-service_user",
            "sub": "10",
            "guid": guid,
            "resource_paths": ["/my/resource/path1", "/path2"],
            "action": "download",
        }
        request_data.update(test_data)
        res = client.post(
            "/log/presigned_url",
            json=request_data,
            headers={"Authorization": f"bearer {fake_jwt}"},
        )
        assert res.status_code == 201, res.text


@pytest.mark.skip(reason="Not implemented yet")
def test_query_field_filter(client):
    submit_test_data(client)

    # query all logs
    res = client.get(
        "/log/presigned_url", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    response_data = res.json()["data"]
    assert len(response_data) == len(PRESIGNED_URL_TEST_DATA)

    # query logs for 1 user
    res = client.get(
        "/log/presigned_url?username=userA",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    response_data = res.json()["data"]
    assert len(response_data) == 4
    assert all(log["username"] == "userA" for log in response_data)

    # query logs for 1 guid
    res = client.get(
        "/log/presigned_url?guid=guid2", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    response_data = res.json()["data"]
    assert len(response_data) == 1
    assert all(log["guid"] == "guid2" for log in response_data)

    # query logs for 1 user, 1 guid
    res = client.get(
        "/log/presigned_url?username=userA&guid=guid1",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    response_data = res.json()["data"]
    assert len(response_data) == 2
    assert all(log["username"] == "userA" for log in response_data)
    assert all(log["guid"] == "guid1" for log in response_data)

    # query logs for 2 guids
    res = client.get(
        "/log/presigned_url?guid=guid2&guid=guid3",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    response_data = res.json()["data"]
    assert len(response_data) == 2
    assert all(log["guid"] in ["guid2", "guid3"] for log in response_data)

    # query logs for 1 user, 2 guids
    res = client.get(
        "/log/presigned_url?username=userA&guid=guid1&guid=guid3",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    response_data = res.json()["data"]
    assert len(response_data) == 3
    assert all(log["username"] == "userA" for log in response_data)
    assert all(log["guid"] in ["guid1", "guid3"] for log in response_data)


@pytest.mark.skip(reason="Not implemented yet")
def test_query_groupby(client):
    submit_test_data(client)

    # query logs grouped by username
    res = client.get(
        "/log/presigned_url?groupby=username",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    response_data = res.json()["data"]
    # TODO

    # query logs grouped by username and guid
    res = client.get(
        "/log/presigned_url?groupby=username&groupby=guid",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    response_data = res.json()["data"]
    # TODO

    # query logs grouped by username with filter
    res = client.get(
        "/log/presigned_url?groupby=username&username=userA",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    response_data = res.json()["data"]
    # TODO

    # query logs grouped by username with start and stop timestamps
    start = timestamp_for_date("2020/02/01")
    stop = timestamp_for_date("2020/04/01")
    res = client.get(
        f"/log/presigned_url?groupby=username&start={start}&stop={stop}",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    response_data = res.json()["data"]
    # TODO


@pytest.mark.skip(reason="Not implemented yet")
def test_query_timestamps(client):
    # TODO
    pass


@pytest.mark.skip(reason="Not implemented yet")
def test_query_pagination(client):
    # TODO
    pass


@pytest.mark.skip(reason="Not implemented yet")
def test_query_count(client):
    # TODO
    pass
