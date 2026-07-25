import os
import unittest
from unittest.mock import patch
import urllib.error

from src.network import check_https_endpoint, configure_network_security


class NetworkSecurityTests(unittest.TestCase):
    def test_bundled_ca_is_configured_for_https_clients(self) -> None:
        ca_bundle = configure_network_security()

        self.assertTrue(ca_bundle.is_file())
        self.assertEqual(os.environ["SSL_CERT_FILE"], str(ca_bundle))
        self.assertEqual(os.environ["REQUESTS_CA_BUNDLE"], str(ca_bundle))

    @patch("src.network.urllib.request.urlopen")
    def test_connectivity_check_accepts_any_http_response(self, urlopen) -> None:
        urlopen.side_effect = urllib.error.HTTPError(
            "https://cdn.example/", 404, "Not Found", {}, None
        )

        result = check_https_endpoint(
            "cdn.example", "https://cdn.example/", "media"
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["status"], 404)

    @patch("src.network.urllib.request.urlopen")
    def test_connectivity_check_reports_dns_failure(self, urlopen) -> None:
        urlopen.side_effect = urllib.error.URLError(
            __import__("socket").gaierror("not found")
        )

        result = check_https_endpoint(
            "cdn.example", "https://cdn.example/", "media"
        )

        self.assertFalse(result["available"])
        self.assertEqual(result["error"], "ошибка DNS")


if __name__ == "__main__":
    unittest.main()
