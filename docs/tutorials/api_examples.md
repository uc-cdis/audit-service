# API example requests

#### How many times was the file of GUID "XYZ" downloaded in the past year?

Query: `<Audit service URL>/log/presigned_url?action=download&guid=XYZ&status_code=200&start=<timestamp for Jan 1st>&stop=<timestamp for Dec 31st>&count`

- The category is `presigned_url` because file download and upload requests are made through Fence presigned URLs;
- Set the action to `download` to filter out "upload file" requests;
- Select the relevant file by filtering on the `guid`;
- Set the status code to `200` to filter out unsuccessful requests, where the user was not able to download the file;
- Use the `start` and `stop` parameters to limit the query to the past year. The values should be Epoch timestamps;
- Use the `count` flag to get the number of logs instead of the actual logs.
