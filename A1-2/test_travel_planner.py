import argparse
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

import travel_planner


class TravelPlannerTest(unittest.TestCase):
    def test_valid_date(self):
        self.assertEqual(travel_planner.valid_date("2026-09-15"), "2026-09-15")
        with self.assertRaises(argparse.ArgumentTypeError):
            travel_planner.valid_date("2026-02-30")

    def test_extract_json_from_code_block(self):
        data = travel_planner.extract_json('```json\n{"recommended_city": "제주"}\n```')
        self.assertEqual(data["recommended_city"], "제주")

    def test_validate_recommendation(self):
        data = {"recommended_city": "강릉", "weather": "맑음", "events": ["축제"], "reason": "추천 이유"}
        self.assertEqual(travel_planner.validate_recommendation(data), data)

    def test_validate_recommendation_rejects_missing_key(self):
        with self.assertRaises(travel_planner.ApiCallError):
            travel_planner.validate_recommendation({"recommended_city": "강릉"})

    def test_fallback_report_without_places(self):
        recommendation = {"recommended_city": "제주", "weather": "온화함", "events": [], "reason": "추천 이유"}
        report = travel_planner.render_fallback_report("2026-09-15", recommendation, [], [])
        self.assertIn("## 맛집 추천", report)
        self.assertIn("데이터 없음", report)

    @patch("travel_planner.get_json")
    def test_search_places_converts_kakao_fields(self, mock_get_json):
        mock_get_json.return_value = {
            "documents": [
                {
                    "place_name": "테스트 식당",
                    "road_address_name": "제주특별자치도 테스트로 1",
                    "category_name": "음식점",
                    "place_url": "https://place.map.kakao.com/1",
                    "x": "126.1",
                    "y": "33.1",
                }
            ]
        }
        places = travel_planner.search_places("제주", "test-key")
        self.assertEqual(places[0]["name"], "테스트 식당")
        self.assertEqual(places[0]["lat"], 33.1)

    def test_save_results(self):
        recommendation = {"recommended_city": "제주", "weather": "온화함", "events": [], "reason": "추천 이유"}
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(travel_planner, "RESULTS_DIR", Path(temp_dir)):
            raw_path, report_path = travel_planner.save_results("2026-09-15", recommendation, [], [], "# 리포트")
            self.assertTrue(raw_path.exists())
            self.assertEqual(report_path.read_text(encoding="utf-8"), "# 리포트")

    def test_get_codyssey_api_url(self):
        with patch.dict(os.environ, {"CODYSSEY_API_BASE_URL": "https://api.example.com/"}, clear=True):
            self.assertEqual(
                travel_planner.get_codyssey_api_url(),
                "https://api.example.com/v1/chat/completions",
            )

    def test_get_codyssey_api_url_uses_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                travel_planner.get_codyssey_api_url(),
                "https://copa.codyssey.kr/v1/chat/completions",
            )


if __name__ == "__main__":
    unittest.main()
