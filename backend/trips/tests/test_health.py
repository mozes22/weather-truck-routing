from typing import Any

from django.test import SimpleTestCase
from rest_framework.test import APIClient


class HealthTests(SimpleTestCase):
    def test_health_returns_ok(self):
        # DRF has no type stubs, so the checker guesses the wrong type. Any is like TypeScript's any.
        response: Any = APIClient().get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
