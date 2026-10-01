# JobSpy API for Cloudron

Cloudron community package wrapping [JobSpy](https://github.com/speedyapply/JobSpy) in a small, authenticated JSON API. Source: https://github.com/ericm115/jobspy-cloudron. Image: `docker.io/emoralesjw/jobspy-cloudron`. Requires Cloudron 10.0.0 or newer. JobSpy scrapes third-party boards; results and availability depend on those boards and their rate limits.

## Install and use

Add this URL under Cloudron **Community apps**:

`https://raw.githubusercontent.com/ericm115/jobspy-cloudron/main/CloudronVersions.json`

Cloudron installs the published image and provides HTTPS. On first start, `start.sh` generates a random key at `/app/data/api-key`. Use the app's Cloudron terminal to read it; never commit, log, or send it in a URL. `/app/data` is persistent and backed up by Cloudron. Restart preserves the key; restore from backup also restores it. Key must contain at least 32 characters. If the key is lost, remove `/app/data/api-key` and restart the app to create a new one; existing clients then need the new key. To rotate, replace the file with a freshly generated key, restrict access to the app user, then restart (the server reads the key only at startup). On Cloudron, use HTTPS, not HTTP.

`distance` is available in published version `0.1.1` and newer; version `0.1.0` rejects it.

`GET /health` returns `{"status":"ok"}` without authentication. `POST /scrape` requires `Authorization: Bearer <key>`, `Content-Type: application/json`, and a JSON object body. Example PowerShell request (replace placeholders; do not save a real key in source):

```powershell
$key = '<key from Cloudron terminal>'
$body = '{"site_name":["indeed"],"search_term":"software engineer","location":"Austin, TX","results_wanted":2,"hours_old":72,"distance":25}'
Invoke-RestMethod -Uri 'https://<app-domain>/scrape' -Method Post -ContentType 'application/json' -Headers @{Authorization="Bearer $key"} -Body $body
```

Response: `{"jobs":[{"site":"indeed","title":"...","company":"...","job_url":"..."}]}`. Actual fields come from JobSpy; empty results return `{"jobs":[]}`. Supported `site_name` values: `indeed`, `linkedin`, `zip_recruiter`, `glassdoor`, `google`, `bayt`, `naukri`, `bdjobs`; default is `["indeed"]`. Supply 1–3 distinct sites. `google` requires `google_search_term`. Provide `search_term` or `google_search_term`. Optional: `location`, `country_indeed` (strings, at most 200 characters), `results_wanted` (integer 1–25, default 10 **per site**), `hours_old` (integer 1–8760), `distance` (integer 1–200 miles; JobSpy defaults to 50 if omitted). Request body limit: 4096 bytes. Other fields, including client-specified proxies, are rejected. Responses: `400` invalid request; `401` missing/wrong key; `429` scrape already running; `502` scrape error. Only one scrape runs at once. A stalled upstream scrape currently has no application-level timeout; restart app if it remains stuck. `/health` only checks HTTP service, not job-board connectivity.

## Development and release

Relevant files: `app.py` (API, validation, scraping), `start.sh` (key creation, permissions, unprivileged start), `Dockerfile` (pinned Cloudron Python base and `python-jobspy==1.1.82`), `CloudronManifest.json` (app config), `CloudronVersions.json` (published version catalog), `test_app.py` (stdlib tests), `icon.svg` and `banner.svg` (public catalog assets). Runtime writes only to Cloudron's `/app/data`, `/run`, or `/tmp`; API key lives in `/app/data`. Default memory is 1 GiB (`memoryLimit`).

Run local tests without Docker:

```powershell
python -B -m unittest -v test_app
cloudron versions verify
```

Tests mock JobSpy and check auth, validation, response, busy status, and weak/missing-key startup. Before each release, also build and smoke-test **the new image**: health, unauthorized requests, one small real scrape, and JSON result fields. Test on a non-production Cloudron instance if available. Scraping reliability and Cloudron runtime cannot be proved by mocked tests alone.

Release steps (replace `X.Y.Z` with **new** semver, not an existing release):

1. Change `version` and `changelog` in `CloudronManifest.json`; update pinned JobSpy/base version in `Dockerfile` only if tested. Keep app ID `com.jobworks.jobspy`. Run tests and build/test image under the intended Docker context.
2. Build and push `docker.io/emoralesjw/jobspy-cloudron:X.Y.Z` using an account with namespace push rights. Confirm Docker Hub repository is public and verify image can be pulled **without registry credentials**. Never put a credential in source or catalog.
3. Run `cloudron versions add --image docker.io/emoralesjw/jobspy-cloudron:X.Y.Z`, then `cloudron versions verify`. Inspect embedded manifest, `dockerImage`, and `publishState` in `CloudronVersions.json`. The catalog entry embeds a snapshot; updating only `CloudronManifest.json` does not change previously added entries. For a testing release, use `--state testing`; publish it only after validation with `cloudron versions update --version X.Y.Z --state published` and verify again.
4. Commit and push only intended source/catalog/assets to GitHub `main`. Confirm raw catalog URL and asset URLs return successfully; verify catalog references public image. Cloudron community-app installations then see published updates. Do **not** edit an already published version or reuse its Docker tag: create a new version instead; use `cloudron versions revoke` for a critical bad published version.

Do not run Docker, publish, or deploy as part of ordinary tests. Cloudron's [publishing](https://docs.cloudron.io/packaging/publishing/), [versions](https://docs.cloudron.io/packaging/versions/), and [manifest](https://docs.cloudron.io/packaging/manifest/) docs define current catalog rules. No Cloudron production install was performed during the initial release; validate on your server before relying on it.
