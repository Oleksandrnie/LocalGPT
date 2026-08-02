import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import meta


class CaddyRootCertificateRouteTestCase(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(meta.router)
        self.client = TestClient(app)

    def test_downloads_public_root_certificate_only_when_lan_is_live(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            certificate = Path(temp_dir) / "root.crt"
            certificate.write_text("public certificate", encoding="utf-8")
            with (
                patch("app.routes.meta._get_lan_url", return_value="https://192.168.1.20:8443/ui/gui_html.html"),
                patch("app.routes.meta._caddy_root_ca_path", return_value=certificate),
            ):
                response = self.client.get("/network/caddy/root-ca")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"public certificate")
        self.assertEqual(response.headers["content-type"], "application/x-x509-ca-cert")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("attachment; filename=\"localgpt-caddy-root-ca.crt\"", response.headers["content-disposition"])

    @patch("app.routes.meta._get_lan_url", return_value=None)
    def test_rejects_certificate_download_when_lan_proxy_is_unavailable(self, _mock_lan_url):
        response = self.client.get("/network/caddy/root-ca")

        self.assertEqual(response.status_code, 404)

    def test_rejects_symlinked_certificate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "target.crt"
            certificate = root / "root.crt"
            target.write_text("public certificate", encoding="utf-8")
            certificate.symlink_to(target)
            with (
                patch("app.routes.meta._get_lan_url", return_value="https://192.168.1.20:8443/ui/gui_html.html"),
                patch("app.routes.meta._caddy_root_ca_path", return_value=certificate),
            ):
                response = self.client.get("/network/caddy/root-ca")

        self.assertEqual(response.status_code, 404)
