"""Tests for the review in pipeline.py: make ci-test"""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline  # noqa: E402

TICKETS = ["DEMO-101", "DEMO-102"]


def make_review(*statuses):
    """A model reply: DEMO-101 with one criterion per status, DEMO-102 met."""
    return {
        "tickets": [
            {"ticket": "DEMO-101", "title": "Baseline", "criteria": [
                {"criterion": f"criterion {i}", "status": status, "evidence": "locals.tf"}
                for i, status in enumerate(statuses or ("met",))
            ]},
            {"ticket": "DEMO-102", "title": "Move Brian", "criteria": [
                {"criterion": "Brian is in Retail Banking", "status": "met", "evidence": "locals.tf"},
            ]},
        ],
        "concerns": [],
        "summary": "",
    }


class DecideTest(unittest.TestCase):
    def test_every_criterion_met_passes(self):
        review = pipeline.decide(make_review("met", "met"), TICKETS)
        self.assertEqual(review["verdict"], "pass")
        self.assertEqual(review["checks"], [])

    def test_any_criterion_not_met_fails(self):
        self.assertEqual(pipeline.decide(make_review("met", "not_met"), TICKETS)["verdict"], "fail")

    def test_not_met_fails_even_with_unclear(self):
        self.assertEqual(pipeline.decide(make_review("unclear", "not_met"), TICKETS)["verdict"], "fail")

    def test_unclear_criterion_needs_a_human(self):
        self.assertEqual(pipeline.decide(make_review("met", "unclear"), TICKETS)["verdict"], "needs_human")

    def test_ticket_missing_from_the_reply_needs_a_human(self):
        review = pipeline.decide(make_review(), TICKETS + ["DEMO-103"])
        self.assertEqual(review["verdict"], "needs_human")
        self.assertEqual(review["checks"], ["no result for DEMO-103"])

    def test_ticket_without_criteria_needs_a_human(self):
        reply = make_review()
        reply["tickets"][1]["criteria"] = []
        review = pipeline.decide(reply, TICKETS)
        self.assertEqual(review["verdict"], "needs_human")
        self.assertEqual(review["checks"], ["DEMO-102: no criteria checked"])

    def test_verdict_from_the_model_is_ignored(self):
        reply = make_review("not_met")
        reply["verdict"] = "pass"
        self.assertEqual(pipeline.decide(reply, TICKETS)["verdict"], "fail")


class ParseReviewTest(unittest.TestCase):
    def test_reads_bare_json_and_a_json_code_block(self):
        reply = make_review()
        self.assertEqual(pipeline.parse_review(json.dumps(reply)), reply)
        self.assertEqual(pipeline.parse_review(f"```json\n{json.dumps(reply)}\n```"), reply)

    def test_rejects_a_reply_without_tickets(self):
        self.assertIsNone(pipeline.parse_review("not json"))
        self.assertIsNone(pipeline.parse_review(json.dumps({"summary": ""})))
        self.assertIsNone(pipeline.parse_review("[]"))


class TicketsTest(unittest.TestCase):
    def test_every_ticket_is_loaded_with_its_id(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("DEMO-2.md", "DEMO-1.md"):
                (Path(directory) / name).write_text(f"# {name}")
            text, ids = pipeline.load_tickets(directory)
        self.assertEqual(ids, ["DEMO-1", "DEMO-2"])
        self.assertIn("# DEMO-1.md", text)
        self.assertIn("# DEMO-2.md", text)


class MessageTest(unittest.TestCase):
    def test_message_holds_tickets_configuration_and_policies(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "policies").mkdir()
            (Path(directory) / "policies" / "mask.yaml").write_text("name: Mask names")
            context = {"users": {"brian": {}}, "groups": {}, "tags": [], "policies": {"policies/mask.yaml": {}}}
            with mock.patch.object(pipeline, "ROOT", Path(directory)):
                message = pipeline.build_message("# DEMO-1: Ticket", context)
        self.assertIn("BEGIN TICKETS", message)
        self.assertIn("# DEMO-1: Ticket", message)
        self.assertIn('"brian"', message)
        self.assertIn("name: Mask names", message)


class OllamaTest(unittest.TestCase):
    def test_request_holds_the_model_to_the_review_schema(self):
        reply = make_review()
        response = io.BytesIO(json.dumps({"message": {"content": json.dumps(reply)}}).encode())
        with mock.patch.object(pipeline.urllib.request, "urlopen") as urlopen, \
                mock.patch.dict(pipeline.os.environ, {}, clear=True), mock.patch("builtins.print"):
            urlopen.return_value.__enter__.return_value = response
            content = pipeline.Ollama("some-model", 32768).ask("title", "material")

        request = urlopen.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "http://localhost:11434/api/chat")
        self.assertEqual(body["model"], "some-model")
        self.assertEqual(body["options"]["num_ctx"], 32768)
        self.assertEqual(body["format"], pipeline.REVIEW_SCHEMA)
        self.assertEqual(pipeline.parse_review(content), reply)


if __name__ == "__main__":
    unittest.main()
