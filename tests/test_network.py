import os
import unittest

from src.network import configure_network_security


class NetworkSecurityTests(unittest.TestCase):
    def test_bundled_ca_is_configured_for_https_clients(self) -> None:
        ca_bundle = configure_network_security()

        self.assertTrue(ca_bundle.is_file())
        self.assertEqual(os.environ["SSL_CERT_FILE"], str(ca_bundle))
        self.assertEqual(os.environ["REQUESTS_CA_BUNDLE"], str(ca_bundle))


if __name__ == "__main__":
    unittest.main()
