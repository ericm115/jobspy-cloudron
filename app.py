"""Small, private Cloudron HTTP adapter for JobSpy."""
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEY_PATH = os.environ.get("JOBSPY_KEY_PATH", "/app/data/api-key")
SITES = {"indeed", "linkedin", "zip_recruiter", "glassdoor", "google", "bayt", "naukri", "bdjobs"}
FIELDS = {"site_name", "search_term", "google_search_term", "location", "results_wanted", "hours_old", "distance", "country_indeed", "fetch_description"}
BUSY = threading.BoundedSemaphore(1)


def validate(data):
    if not isinstance(data, dict) or data.keys() - FIELDS:
        raise ValueError("invalid fields")
    sites = data.get("site_name", ["indeed"])
    if not isinstance(sites, list) or not sites or len(sites) > 3 or any(
        not isinstance(site, str) or site not in SITES for site in sites
    ) or len(set(sites)) != len(sites):
        raise ValueError("site_name must list 1-3 distinct supported sites")
    params = {"site_name": sites}
    for field in ("search_term", "google_search_term", "location", "country_indeed"):
        if field in data:
            value = data[field]
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError(f"invalid {field}")
            params[field] = value
    if not ("search_term" in params or "google_search_term" in params):
        raise ValueError("search_term or google_search_term required")
    if "google" in sites and "google_search_term" not in params:
        raise ValueError("google_search_term required for google")
    for field, minimum, maximum, default in (("results_wanted", 1, 25, 10), ("hours_old", 1, 8760, None), ("distance", 1, 200, None)):
        value = data.get(field, default)
        if field in data and (type(value) is not int or not minimum <= value <= maximum):
            raise ValueError(f"invalid {field}")
        if value is not None:
            params[field] = value
    if "fetch_description" in data:
        if type(data["fetch_description"]) is not bool:
            raise ValueError("invalid fetch_description")
        # ponytail: pinned JobSpy 1.1.82 supports description fetching for LinkedIn only; revisit on upgrade.
        params["linkedin_fetch_description"] = data["fetch_description"]
    return params


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, payload):
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"status": "ok"})
        else:
            self.respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/scrape":
            self.respond(404, {"error": "not found"})
            return
        token = self.headers.get("Authorization", "")
        if not hmac.compare_digest(token.encode("utf-8"), ("Bearer " + self.server.api_key).encode("ascii")):
            self.respond(401, {"error": "unauthorized"})
            return
        if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self.respond(400, {"error": "expected JSON body with Content-Length"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 4096:
                raise ValueError("invalid body size")
            params = validate(json.loads(self.rfile.read(length)))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.respond(400, {"error": str(exc)})
            return
        if not BUSY.acquire(blocking=False):
            self.respond(429, {"error": "scrape already running"})
            return
        try:
            from jobspy import scrape_jobs
            jobs = scrape_jobs(**params)
            result = json.loads(jobs.to_json(orient="records", date_format="iso"))
        except Exception:
            self.log_error("scrape failed")
            self.respond(502, {"error": "scrape failed; check server logs"})
            return
        finally:
            BUSY.release()
        self.respond(200, {"jobs": result})


if __name__ == "__main__":
    with open(KEY_PATH, encoding="ascii") as key_file:
        key = key_file.read().strip()
    if len(key) < 32:
        raise SystemExit("api-key missing or too short")
    with ThreadingHTTPServer(("0.0.0.0", 8000), Handler) as server:
        server.api_key = key
        server.serve_forever()
