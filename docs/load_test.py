"""
To run this load test in a Dev or QA environment, you need to:

- Allow POSTing audit logs externally: edit the configuration file at
`~/cloud-automation/kube/services/revproxy/gen3.nginx.conf/audit-service.conf`
and comment out the following block:
    limit_except GET {
        deny all;
    }
- Make sure the environment's audit-service configuration file does not set
`QUERY_TIMEBOX_MAX_DAYS` since that would stop you from querying all the
logs at once.
"""


from datetime import datetime
import json
from random import randint
import requests
import time


base_url = "https://qa-niaid.planx-pla.net"
path_to_api_key = ""
n_logs = 10000


def get_token():
    with open(path_to_api_key, "r") as f:
        creds = json.load(f)
    token_url = base_url + "/user/credentials/api/access_token"
    resp = requests.post(token_url, json=creds)
    if resp.status_code != 200:
        print(resp.text)
        raise Exception(resp.reason)
    return resp.json()["access_token"]


def timestamp_for_date(date_string):
    """
    Input: date in format YYYY-MM-DD (str)
    Output: timestamp (int)
    """
    dt = datetime.strptime(date_string, "%Y/%m/%d")
    return int(datetime.timestamp(dt))


def submit_a_lot():
    guid_base = "dg.fake/b01ebf46-3832-4a75-8736-b09e8d9fd"
    start = time.time()
    for i in range(n_logs):
        if n_logs > 500 and i % 500 == 0:
            print(f"Submitting test data: {i}/{n_logs}")
        guid = f"{guid_base}{randint(0, 999):03d}"
        user = f"user_{randint(0, 99):02d}"
        date = f"{randint(2000, 2025)}/{randint(1, 12)}/{randint(1, 28)}"
        request_data = {
            "request_url": f"/data/download/{guid}",
            "status_code": 200,
            "username": user,
            "sub": 10,
            "guid": guid,
            "resource_paths": ["/my/resource/path1", "/path2"],
            "action": "download",
            "timestamp": timestamp_for_date(date),
        }
        res = requests.post(f"{base_url}/audit/log/presigned_url", json=request_data)
        assert res.status_code == 201, res.text
    print(f"Submitted {n_logs} audit logs in {time.time() - start:.1f}s")


def query_a_lot(headers):
    total_logs = 0
    next_timestamp = None
    done = False
    i = 0
    query_url = f"{base_url}/audit/log/presigned_url"
    start = time.time()
    while not done:
        print(f"Querying page {i}")
        url = query_url
        if next_timestamp:
            url = f"{query_url}?start={next_timestamp}"
        res = requests.get(url, headers=headers)
        assert res.status_code == 200, f"{res.text}\n{url}"
        response_data = res.json()["data"]
        return
        next_timestamp = res.json()["nextTimeStamp"]
        total_logs += len(response_data)
        if not next_timestamp:
            done = True
        i += 1
    if total_logs < n_logs:
        print(
            f"Something went wrong - we submitted {n_logs} logs and only queried {total_logs}"
        )
    if total_logs > n_logs:
        print("FYI the database already contained audit logs")
    print(f"Queried {total_logs} audit logs in {time.time() - start:.1f}s (no filters)")


def query_a_lot_groupby(headers):
    next_timestamp = None
    done = False
    i = 0
    url = f"{base_url}/audit/log/presigned_url?groupby=username"
    start = time.time()
    res = requests.get(url, headers=headers)
    assert res.status_code == 200, f"{res.text}\n{url}"
    response_data = res.json()["data"]
    next_timestamp = res.json()["nextTimeStamp"]
    end = time.time() - start
    count = sum(r["count"] for r in response_data)
    print(f"Queried {count} audit logs in {end:.1f}s (groupby)")


if __name__ == "__main__":
    submit_a_lot()
    headers = {"Authorization": "bearer " + get_token()}
    query_a_lot(headers)
    query_a_lot_groupby(headers)
