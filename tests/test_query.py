from datetime import datetime
import pytest
from random import randint
import time

from audit.config import config


def timestamp_for_date(date_string, format="%Y/%m/%d"):
    """
    Input: date in format YYYY-MM-DD (str)
    Output: timestamp (int)
    """
    dt = datetime.strptime(date_string, format)
    return int(datetime.timestamp(dt))


PRESIGNED_URL_TEST_DATA = {
    "A1_1": {
        "username": "userA",
        "guid": "guid1",
        "timestamp": timestamp_for_date("2020/01/16"),
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
        "timestamp": timestamp_for_date("2020/01/15"),
        "resource_paths": ["/other/resource/path"],
    },
}

fake_jwt = "1.2.3"


def submit_test_data(client, n=len(PRESIGNED_URL_TEST_DATA)):
    """
    Submit a set of presigned URL audit logs
    """
    i = 0
    while i < n:
        for test_data in PRESIGNED_URL_TEST_DATA.values():
            if i == n:
                break
            guid = "dg.hello/abc"
            request_data = {
                "request_url": f"/request_data/download/{guid}",
                "status_code": 200,
                "username": "audit-service_user",
                "sub": 10,
                "guid": guid,
                "resource_paths": ["/my/resource/path1", "/path2"],
                "action": "download",
            }
            request_data.update(test_data)
            res = client.post("/log/presigned_url", json=request_data)
            assert res.status_code == 201, res.text
            i += 1


def test_query_field_filter(client):
    submit_test_data(client)

    # query all logs
    res = client.get(
        "/log/presigned_url", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == len(PRESIGNED_URL_TEST_DATA)  # all test logs
    # make sure logs are ordered by increasing timestamp:
    previous_timestamp = 0
    for log in response_data:
        date = log["timestamp"].split("T")[0]
        timestamp = timestamp_for_date(date, format="%Y-%m-%d")
        assert timestamp > previous_timestamp
        previous_timestamp = timestamp

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
    for i, item in enumerate(response_data):
        test_data = PRESIGNED_URL_TEST_DATA[
            "B1" if i == 0 else ("A2" if i == 1 else "A3")
        ]
        assert item["username"] == test_data["username"]
        assert item["guid"] == test_data["guid"]
        assert item["resource_paths"] == test_data["resource_paths"]

    # query with a field that doesn't exist for this category
    res = client.get(
        "/log/presigned_url?whatisthis=yes",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 400, res.text


def test_query_no_logs(client):
    # query all logs
    res = client.get(
        "/log/presigned_url", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 0

    # query logs grouped by username
    res = client.get(
        "/log/presigned_url?groupby=username",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert response_data == []


def test_query_groupby(client, monkeypatch):
    submit_test_data(client)

    # query logs grouped by username
    res = client.get(
        "/log/presigned_url?groupby=username",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    expected = [
        {"username": "userA", "count": 4},
        {"username": "userB", "count": 1},
    ]
    assert sorted(response_data, key=lambda e: e["username"]) == expected

    # query logs grouped by username and guid
    res = client.get(
        "/log/presigned_url?groupby=username&groupby=guid",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    expected = [
        {"username": "userA", "guid": "guid1", "count": 2},
        {"username": "userA", "guid": "guid2", "count": 1},
        {"username": "userA", "guid": "guid3", "count": 1},
        {"username": "userB", "guid": "guid1", "count": 1},
    ]
    assert sorted(response_data, key=lambda e: (e["username"], e["guid"])) == expected

    # query logs grouped by username with username filter
    res = client.get(
        "/log/presigned_url?groupby=username&username=userA",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    expected = [{"username": "userA", "count": 4}]
    assert response_data == expected

    # query logs grouped by guid with username filter
    res = client.get(
        "/log/presigned_url?groupby=guid&username=userA",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    expected = [
        {"guid": "guid1", "count": 2},
        {"guid": "guid2", "count": 1},
        {"guid": "guid3", "count": 1},
    ]
    assert sorted(response_data, key=lambda e: (e["guid"])) == expected

    # query logs grouped by username with start and stop timestamps
    start = timestamp_for_date("2020/02/01")
    stop = timestamp_for_date("2020/04/01")
    res = client.get(
        f"/log/presigned_url?groupby=username&start={start}&stop={stop}",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    expected = [{"username": "userA", "count": 2}]
    assert response_data == expected

    # query logs grouped by timestamp
    res = client.get(
        "/log/presigned_url?groupby=timestamp&guid=guid1",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 3
    assert all(log["count"] == 1 for log in response_data)

    # make sure the page limit is ignored for groupby queries:
    # set the page limit to 1 and query logs grouped by username
    monkeypatch.setitem(config, "QUERY_PAGE_SIZE", 1)
    res = client.get(
        "/log/presigned_url?groupby=username",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    expected = [
        {"username": "userA", "count": 4},
        {"username": "userB", "count": 1},
    ]
    assert sorted(response_data, key=lambda e: e["username"]) == expected

    # query with a groupby field that doesn't exist for this category
    res = client.get(
        "/log/presigned_url?groupby=whatisthis",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 400, res.text


def test_query_timestamps(client, monkeypatch):
    """
    Queries are time-boxed: if (stop-timestamp - start-timestamp) is greater
    than the configured MAX (`QUERY_TIMEBOX_MAX_DAYS`), we return an error.
    """
    submit_test_data(client)

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


def test_query_pagination(client, monkeypatch):
    submit_test_data(client)

    page_size = 2
    monkeypatch.setitem(config, "QUERY_PAGE_SIZE", page_size)

    total_logs = 0
    next_timestamp = None
    done = False
    while not done:
        url = "/log/presigned_url"
        if next_timestamp:
            url += f"?start={next_timestamp}"
        res = client.get(url, headers={"Authorization": f"bearer {fake_jwt}"})
        assert res.status_code == 200, res.text
        response_data = res.json()["data"]
        next_timestamp = res.json()["nextTimeStamp"]
        total_logs += len(response_data)
        if not next_timestamp:
            done = True
            assert total_logs == len(PRESIGNED_URL_TEST_DATA)
            assert len(response_data) == len(PRESIGNED_URL_TEST_DATA) % page_size
        else:
            assert next_timestamp
            assert len(response_data) == page_size


def test_query_pagination_edge_case(client, monkeypatch):
    """
    TODO
    """
    # submit audit logs
    guid = "dg.hello/abc"
    request_data = {
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
    }
    dates = ["1999/01/01", "2000/01/01", "2009/01/01"]
    for date in dates:
        timestamp = timestamp_for_date(date)
        for _ in range(2):
            res = client.post(
                "/log/presigned_url", json={"timestamp": timestamp, **request_data}
            )
            assert res.status_code == 201, res.text

    # now we should have 6 logs: [1999, 1999, 2000, 2000, 2009, 2009]

    page_size = 3
    monkeypatch.setitem(config, "QUERY_PAGE_SIZE", page_size)

    # query the 1st page
    url = "/log/presigned_url"
    res = client.get(url, headers={"Authorization": f"bearer {fake_jwt}"})
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    next_timestamp = res.json()["nextTimeStamp"]
    assert len(response_data) == 4  # not page_size!
    assert response_data[0]["timestamp"] == "1999-01-01T00:00:00"
    assert response_data[1]["timestamp"] == "1999-01-01T00:00:00"
    assert response_data[2]["timestamp"] == "2000-01-01T00:00:00"
    assert response_data[3]["timestamp"] == "2000-01-01T00:00:00"
    assert next_timestamp

    # query the 2nd page
    res = client.get(
        f"{url}?start={next_timestamp}", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    next_timestamp = res.json()["nextTimeStamp"]
    assert len(response_data) == 2
    assert response_data[0]["timestamp"] == "2009-01-01T00:00:00"
    assert response_data[1]["timestamp"] == "2009-01-01T00:00:00"
    assert not next_timestamp


def test_query_category(client):
    submit_test_data(client, 1)

    # submit a login audit log
    request_data = {
        "request_url": "/login",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "timestamp": timestamp_for_date("2020/01/01"),
        "idp": "google",
    }
    res = client.post("/log/login", json=request_data)
    assert res.status_code == 201, res.text

    # query presigned_url logs
    res = client.get(
        "/log/presigned_url", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 1
    assert "guid" in response_data[0]
    assert "idp" not in response_data[0]

    # query login logs
    res = client.get("/log/login", headers={"Authorization": f"bearer {fake_jwt}"})
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert len(response_data) == 1
    assert "idp" in response_data[0]
    assert "guid" not in response_data[0]

    # query a category that doesn't exist
    res = client.get("/log/whatisthis", headers={"Authorization": f"bearer {fake_jwt}"})
    assert res.status_code == 400, res.text


def test_query_no_usernames(client, monkeypatch):
    submit_test_data(client)

    monkeypatch.setitem(config, "QUERY_USERNAMES", False)

    # do not return usernames
    res = client.get(
        "/log/presigned_url", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 200, res.text
    response_data = res.json()["data"]
    assert all("username" not in log for log in response_data), response_data

    # do not allow filtering by username
    res = client.get(
        "/log/presigned_url?username=userA",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 400, res.text

    # do not allow grouping by username
    res = client.get(
        "/log/presigned_url?groupby=username",
        headers={"Authorization": f"bearer {fake_jwt}"},
    )
    assert res.status_code == 400, res.text


@pytest.mark.skip(reason="Not implemented yet")
def test_query_count(client):
    # TODO
    pass


def test_query_authz(client, mock_arborist_requests):
    submit_test_data(client)

    # unauthorized requests should get a 403
    mock_arborist_requests(authorized=False)
    res = client.get(
        "/log/presigned_url", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 403, res.text

    # authorized requests should get a 200
    mock_arborist_requests()
    res = client.get(
        "/log/presigned_url", headers={"Authorization": f"bearer {fake_jwt}"}
    )
    assert res.status_code == 200, res.text
