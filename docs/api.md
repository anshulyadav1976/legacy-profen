# Graph Build API

Expose a local HTTP API to upload a repo archive or GitHub URL and return the graph JSON.

## Run

```powershell
.\.venv\Scripts\python -m codeintel.api --host 127.0.0.1 --port 9000
```

## Request

Send a `.zip` archive of your repo folder to `/parse` as `multipart/form-data`.

```powershell
curl -X POST http://127.0.0.1:9000/parse -F "file=@repo.zip"
```

Or provide a GitHub repo URL (or direct zip URL):

```powershell
curl -X POST "http://127.0.0.1:9000/parse?repo_url=https://github.com/spacetelescope/jwst"
```

The API resolves the repo's default branch via the GitHub API when possible, then falls back to `main`/`master`.

Optional query parameter:
- `max_files`: limit parsing for quick checks.

## Response

Returns NetworkX `node_link_data` JSON, compatible with the frontend viewer.
