from datetime import datetime
import pytest  # TODO remove once unused

from audit.config import config


def timestamp_for_date(date_string):
    """
    Input: date in format YYYY-MM-DD (str)
    Output: timestamp (int)
    """
    dt = datetime.strptime(date_string, "%Y/%m/%d")
    return int(datetime.timestamp(dt))


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
        "resource_paths": ["/resource/path/to/query"],
    },
    "A3": {
        "username": "userA",
        "guid": "guid3",
        "timestamp": timestamp_for_date("2020/03/04"),
        "resource_paths": ["/resource/path/to/query", "/other/resource/path"],
    },
    "B1": {
        "username": "userB",
        "guid": "guid1",
        "timestamp": timestamp_for_date("2020/01/16"),
        "resource_paths": ["/other/resource/path"],
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


def test_query_field_filter(client):
    submit_test_data(client)

    # query all logs
    res = client.get(
        "/log/presigned_url", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == len(PRESIGNED_URL_TEST_DATA)  # all test logs

    # query logs for 1 user
    res = client.get(
        "/log/presigned_url?username=userA",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 4  # test logs A1_1, A2_2, A2, A3
    assert all(log["username"] == "userA" for log in response_data)

    # query logs for 1 guid
    res = client.get(
        "/log/presigned_url?guid=guid2", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 1  # test log A2
    assert all(log["guid"] == "guid2" for log in response_data)

    # query logs for 1 user, 1 guid
    res = client.get(
        "/log/presigned_url?username=userA&guid=guid1",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 2  # test logs A1_1, A1_2
    assert all(log["username"] == "userA" for log in response_data)
    assert all(log["guid"] == "guid1" for log in response_data)

    # query logs for 2 guids
    res = client.get(
        "/log/presigned_url?guid=guid2&guid=guid3",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 2  # test logs A2, A3
    assert all(log["guid"] in ["guid2", "guid3"] for log in response_data)

    # query logs for 1 user, 2 guids
    res = client.get(
        "/log/presigned_url?username=userA&guid=guid1&guid=guid3",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    response_data = res.json()["data"]
    assert len(response_data) == 3  # test logs A1_1, A1_2, A3
    assert all(log["username"] == "userA" for log in response_data)
    assert all(log["guid"] in ["guid1", "guid3"] for log in response_data)

    # query logs for a resource path
    res = client.get(
        "/log/presigned_url?resource_paths=/resource/path/to/query",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 2  # test logs A2, A3
    for i, item in enumerate(response_data):
        test_data = PRESIGNED_URL_TEST_DATA["A2" if i == 0 else "A3"]
        assert item["username"] == test_data["username"]
        assert item["guid"] == test_data["guid"]
        assert item["resource_paths"] == test_data["resource_paths"]

    # query logs for 2 resource paths
    res = client.get(
        "/log/presigned_url?resource_paths=/resource/path/to/query&resource_paths=/other/resource/path",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 3  # test logs A2, A3, B1
    print(response_data)
    for i, item in enumerate(response_data):
        test_data = PRESIGNED_URL_TEST_DATA[
            "B1" if i == 0 else ("A2" if i == 1 else "A3")
        ]
        assert item["username"] == test_data["username"]
        assert item["guid"] == test_data["guid"]
        assert item["resource_paths"] == test_data["resource_paths"]


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


def test_query_timestamps(client, monkeypatch):
    submit_test_data(client)

    # queries are time-boxed: if (stop-timestamp - start-timestamp) is greater
    # than MAX, we return an error.

    # query logs with a start timestamp, no stop
    # (stop-timestamp - start-timestamp) < MAX (OK)
    start = timestamp_for_date("2020/03/01")
    res = client.get(
        f"/log/presigned_url?start={start}",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 2  # test logs A1_2, A3
    assert all(log["username"] == "userA" for log in response_data)
    assert all(log["guid"] in ["guid1", "guid3"] for log in response_data)

    # update the config to set the timebox max to 1 month
    monkeypatch.setitem(config, "QUERY_TIMEBOX_MAX_DAYS", 30)

    # query logs with a start timestamp, no stop
    # (stop-timestamp - start-timestamp) > MAX (Error)
    start = timestamp_for_date("2020/03/01")
    res = client.get(
        f"/log/presigned_url?start={start}",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 400, res.text

    # query logs with a stop timestamp, no start
    # (stop-timestamp - start-timestamp) < MAX (OK)
    # Note: the difference cannot be > MAX since "start" is
    # calculated automatically
    stop = timestamp_for_date("2020/03/01")
    res = client.get(
        f"/log/presigned_url?stop={stop}",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 1  # test log A2 is within 1 month of `stop`
    assert response_data[0]["username"] == PRESIGNED_URL_TEST_DATA["A2"]["username"]
    assert response_data[0]["guid"] == PRESIGNED_URL_TEST_DATA["A2"]["guid"]

    # query logs with a start and a stop timestamps
    # (stop-timestamp - start-timestamp) < MAX (OK)
    start = timestamp_for_date("2020/01/01")
    stop = timestamp_for_date("2020/01/30")
    res = client.get(
        f"/log/presigned_url?start={start}&stop={stop}",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 2  # test logs A1_1, B1
    assert all(log["username"] in ["userA", "userB"] for log in response_data)
    assert all(log["guid"] == "guid1" for log in response_data)

    # query logs with a start and a stop timestamps
    # (stop-timestamp - start-timestamp) == MAX (OK)
    start = timestamp_for_date("2020/01/01")
    stop = timestamp_for_date("2020/01/31")
    res = client.get(
        f"/log/presigned_url?start={start}&stop={stop}",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 2  # test logs A1_1, B1
    assert all(log["username"] in ["userA", "userB"] for log in response_data)
    assert all(log["guid"] == "guid1" for log in response_data)

    # query logs with a start and a stop timestamps
    # (stop-timestamp - start-timestamp) > MAX (Error)
    start = timestamp_for_date("2020/01/01")
    stop = timestamp_for_date("2020/01/31") + 1
    res = client.get(
        f"/log/presigned_url?start={start}&stop={stop}",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 400, res.text


@pytest.mark.skip(reason="Not implemented yet")
def test_query_pagination(client):
    # TODO
    pass


@pytest.mark.skip(reason="Not implemented yet")
def test_query_count(client):
    # TODO
    pass


# TODO load test
