"""Offline unit/integration checks. Mocked provider calls are NOT actual AI evidence."""
import io
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from api.recommend import APIError, call_ai, extract_recommendation, handler, validate_input, validate_recommendation

VALID = {"environment": "집", "situation": "작업을 마치고 머리가 복잡해요.", "need": "긴장을 풀고 싶어요."}


def provider_output(course_id="relax", reason="마음을 천천히 내려놓는 시간이 어울려요."):
    return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"course_id": course_id, "reason": reason})}]}]}


class RecommendationTests(unittest.TestCase):
    def test_trims_and_discards_unknown_input(self):
        result = validate_input({**VALID, "environment": " 집 ", "extra": "ignore"})
        self.assertEqual(result, VALID)

    def test_rejects_missing_empty_wrong_types_and_long_input(self):
        invalid = [None, [], {}, {**VALID, "need": "  "}, {**VALID, "need": 123}, {**VALID, "need": "a" * 151}, {**VALID, "situation": "a" * 301}, {**VALID, "environment": "a" * 41}, {**VALID, "need": "a\x00b"}]
        for value in invalid:
            with self.subTest(value_type=type(value).__name__), self.assertRaises(APIError) as error:
                validate_input(value)
            self.assertEqual(error.exception.status, 400)

    def test_all_three_courses_have_server_owned_titles(self):
        for course_id, title in [("focus", "기본 집중 호흡"), ("sleep", "편안한 수면 호흡"), ("relax", "긴장을 푸는 호흡")]:
            result = extract_recommendation(provider_output(course_id))
            self.assertEqual(result["course"], title)

    def test_rejects_bad_ai_shape_ids_and_reasons(self):
        invalid = [{"course_id": "new_course", "reason": "x"}, {"course_id": [], "reason": "x"}, {"course_id": "focus", "reason": " "}, {"course_id": "focus", "reason": "x" * 241}, {"course_id": "focus", "reason": 123}, {"course_id": "focus", "reason": "x", "extra": 1}, None]
        for result in invalid:
            with self.subTest(result_type=type(result).__name__), self.assertRaises(APIError):
                validate_recommendation(result)

    def test_refusal_incomplete_and_malformed_provider_json(self):
        invalid = [{"status": "incomplete", "output": []}, {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]}, {"status": "completed", "output": []}, {"status": "completed", "output": "invalid"}, {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "not-json"}]}]}]
        for response in invalid:
            with self.subTest(response=response), self.assertRaises(APIError):
                extract_recommendation(response)

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    @patch("api.recommend.urllib.request.urlopen")
    def test_missing_key_never_calls_provider(self, request):
        with self.assertRaises(APIError) as error:
            call_ai(VALID)
        self.assertEqual((error.exception.status, error.exception.code), (503, "NOT_CONFIGURED"))
        request.assert_not_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "unit-test-placeholder", "OPENAI_MODEL": ""})
    @patch("api.recommend.urllib.request.urlopen")
    def test_actual_request_contract_with_mocked_transport(self, request):
        request.return_value = io.BytesIO(json.dumps(provider_output()).encode())
        self.assertEqual(call_ai(VALID)["course_id"], "relax")
        sent = request.call_args.args[0]
        payload = json.loads(sent.data)
        self.assertEqual(sent.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(payload["text"]["format"]["schema"]["properties"]["course_id"]["enum"], ["focus", "sleep", "relax"])
        self.assertEqual(payload["model"], "gpt-4.1-mini")
        self.assertFalse(payload["store"])
        self.assertEqual(request.call_args.kwargs["timeout"], 20)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "unit-test-placeholder"})
    def test_provider_timeout_network_and_http_errors(self):
        for provider_error, status, code in [(TimeoutError(), 504, "TIMEOUT"), (urllib.error.URLError(TimeoutError()), 504, "TIMEOUT"), (urllib.error.URLError("offline"), 502, "AI_CONNECTION_ERROR"), (urllib.error.HTTPError("https://api.openai.com", 401, "unauthorized", {}, None), 502, "AI_AUTH_ERROR"), (urllib.error.HTTPError("https://api.openai.com", 429, "limited", {}, None), 429, "AI_RATE_LIMIT"), (urllib.error.HTTPError("https://api.openai.com", 500, "failure", {}, None), 502, "AI_HTTP_ERROR")]:
            with self.subTest(code=code), patch("api.recommend.urllib.request.urlopen", side_effect=provider_error), self.assertRaises(APIError) as error:
                call_ai(VALID)
            self.assertEqual((error.exception.status, error.exception.code), (status, code))
            self.assertNotIn("unit-test-placeholder", str(error.exception))


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/api/recommend"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, body=None, method="POST", content_type="application/json"):
        request = urllib.request.Request(self.url, data=body, headers={"Content-Type": content_type}, method=method)
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, json.loads(response.read())

    def test_rejects_get_and_returns_allow_header(self):
        status, headers, body = self.request(method="GET")
        self.assertEqual(status, 405)
        self.assertEqual(headers["Allow"], "POST")
        self.assertEqual(body["error"]["code"], "METHOD_NOT_ALLOWED")

    def test_http_body_validation_before_ai_call(self):
        cases = [(b"", 400), (b"{oops", 400), (b"null", 400), (b"[]", 400), (b"{}", 400), (b"x" * 4097, 413), (b"\xff", 400)]
        with patch("api.recommend.call_ai") as ai:
            for body, expected in cases:
                with self.subTest(body_length=len(body)):
                    self.assertEqual(self.request(body)[0], expected)
            self.assertEqual(self.request(b"{}", content_type="text/plain")[0], 415)
            ai.assert_not_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_missing_key_response_is_safe_and_not_cached(self):
        with self.assertLogs("rest.recommend", level="WARNING") as logs:
            status, headers, body = self.request(json.dumps(VALID).encode())
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "NOT_CONFIGURED")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertTrue(body["request_id"])
        for value in VALID.values():
            self.assertNotIn(value, "".join(logs.output))

    @patch("api.recommend.call_ai", side_effect=RuntimeError("private details must never leak"))
    def test_unexpected_error_does_not_leak_message(self, _):
        status, _, body = self.request(json.dumps(VALID).encode())
        self.assertEqual(status, 500)
        self.assertNotIn("private details", json.dumps(body))

    @patch("api.recommend.call_ai", return_value={"course_id": "focus", "course": "기본 집중 호흡", "reason": "테스트용 응답"})
    def test_success_json_contract_with_mock_ai(self, _):
        status, headers, body = self.request(json.dumps(VALID).encode())
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"course_id", "course", "reason"})
        self.assertIn("application/json", headers["Content-Type"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
