import os
import sys
import unittest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import weather


class WeatherErrorTests(unittest.TestCase):
    def test_http_error_includes_status(self):
        class DummyResp:
            status_code = 500
            reason = "Internal Server Error"
            text = ""

            def raise_for_status(self):
                raise requests.HTTPError(response=self)

        def fake_get(*args, **kwargs):
            return DummyResp()

        orig_get = weather.requests.get
        weather.requests.get = fake_get
        try:
            msg = weather.get_weather("Paris")
        finally:
            weather.requests.get = orig_get

        self.assertIn("HTTP 500", msg)
        self.assertIn("Internal Server Error", msg)

    def test_network_error_includes_reason(self):
        def fake_get(*args, **kwargs):
            raise requests.ConnectionError("Network down")

        orig_get = weather.requests.get
        weather.requests.get = fake_get
        try:
            msg = weather.get_weather("Paris")
        finally:
            weather.requests.get = orig_get

        self.assertIn("Network down", msg)


if __name__ == "__main__":
    unittest.main()
