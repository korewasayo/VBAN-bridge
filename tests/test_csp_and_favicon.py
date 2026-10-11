import asyncio
import os
import unittest
from contextlib import asynccontextmanager

from config import BASE_DIR
from web.app import create_application


@asynccontextmanager
async def dummy_lifespan(app):
    yield


async def make_asgi_request(app, method="GET", path="/"):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode("ascii"),
        "headers": [(b"host", b"localhost:8000")],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
        "http_version": "1.1",
    }
    response = {"status": None, "headers": {}, "body": bytearray()}
    body_sent = False

    async def receive():
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            response["status"] = message["status"]
            for k, v in message.get("headers", []):
                response["headers"][k.decode("latin1").lower()] = v.decode("latin1")
        elif message["type"] == "http.response.body":
            response["body"].extend(message.get("body", b""))

    await app(scope, receive, send)
    return response


class CspAndFaviconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_application(dummy_lifespan)

    def test_csp_header_allows_external_https_and_blob_images(self):
        res = asyncio.run(make_asgi_request(self.app, "GET", "/login"))
        self.assertEqual(res["status"], 200)
        csp = res["headers"].get("content-security-policy", "")
        self.assertIn("img-src 'self' data: blob: https:;", csp)
        self.assertIn("media-src 'self' blob:;", csp)

    def test_favicon_endpoint_returns_valid_icon(self):
        res = asyncio.run(make_asgi_request(self.app, "GET", "/favicon.ico"))
        self.assertEqual(res["status"], 200)
        self.assertIn("image/x-icon", res["headers"].get("content-type", ""))

    def test_favicon_file_exists_in_static(self):
        icon_path = os.path.join(BASE_DIR, "static", "favicon.ico")
        self.assertTrue(os.path.exists(icon_path), f"Favicon file missing at {icon_path}")
        self.assertGreater(os.path.getsize(icon_path), 0)

    def test_templates_include_favicon_link(self):
        templates_dir = os.path.join(BASE_DIR, "templates")
        template_files = [
            "admin_dashboard.html",
            "admin_login.html",
            "dashboard.html",
            "login.html",
            "request_page.html",
        ]
        for tf in template_files:
            file_path = os.path.join(templates_dir, tf)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn('rel="icon"', content, f"Template {tf} missing favicon link tag")
            self.assertIn('/favicon.ico', content, f"Template {tf} missing /favicon.ico href")


if __name__ == "__main__":
    unittest.main()
