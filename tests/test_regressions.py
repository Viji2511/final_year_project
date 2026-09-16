import unittest
import tempfile
from unittest.mock import patch
from subprocess import CompletedProcess, TimeoutExpired
from fastapi.testclient import TestClient
from api.main import app, results_store
from schemas.ues_schema import UES, BaselineComparison
from agents.stage5_executor_validator import _compare_metrics, _parse_output_metrics, _run_docker_container
from validation import validate_paper_id
from agents.stage2_multimodal.merge import merge_multimodal
from schemas.figure_schema import FigureData

class RegressionTests(unittest.TestCase):
    def setUp(self):
        results_store.clear()
        self.client = TestClient(app)

    def test_api_starts_and_unknown_result_is_404(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/result/missing").status_code, 404)

    def test_invalid_uploads(self):
        for paper_id in ["../escape", "C:escape", "a/b", ""]:
            response = self.client.post("/run", params={"paper_id": paper_id}, files={"file": ("paper.pdf", b"%PDF-test")})
            self.assertEqual(response.status_code, 422)
        response = self.client.post("/run?paper_id=paper_001", files={"file": ("paper.pdf", b"not a PDF")})
        self.assertEqual(response.status_code, 400)

    @patch("api.main.validate_api_keys")
    def test_duplicate_running_paper(self, _keys):
        results_store["paper_001"] = {"status": "running"}
        response = self.client.post("/run?paper_id=paper_001", files={"file": ("paper.pdf", b"%PDF-test")})
        self.assertEqual(response.status_code, 409)

    @patch("api.main.validate_api_keys")
    @patch("api.main.run_pipeline")
    def test_upload_and_background_result(self, pipeline, _keys):
        pipeline.return_value = {"paper_id": "paper_001", "passed": True, "fidelity_score": 1.0}
        with tempfile.TemporaryDirectory() as folder, patch("api.main.PAPERS_DIR", folder):
            response = self.client.post("/run?paper_id=paper_001", files={"file": ("paper.pdf", b"%PDF-test")})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.client.get("/result/paper_001").json()["status"], "complete")
        self.assertEqual(pipeline.call_count, 1)

    def test_missing_metrics_count_as_failures(self):
        ues = UES(paper_id="test", baseline_comparisons=[
            BaselineComparison(model_name="ours", metric="accuracy", value=90),
            BaselineComparison(model_name="ours", metric="f1", value=80)])
        score, mismatches = _compare_metrics({"accuracy": 90}, ues)
        self.assertEqual(score, 0.5)
        self.assertIsNone(mismatches[0]["actual"])
        self.assertEqual(_compare_metrics({}, UES(paper_id="test"))[0], 0)

    def test_caption_matching_uses_page_and_avoids_ambiguity(self):
        figure = FigureData(figure_id="fig_3_1", chart_type="line_chart", page_number=3)
        context = {"figure_captions": [{"label": "Figure 1", "caption": "Actual caption", "page": 3}]}
        merge_multimodal(context, [figure], [], [])
        self.assertEqual(figure.caption, "Actual caption")
        figure.caption = None
        other = FigureData(figure_id="fig_3_2", chart_type="line_chart", page_number=3)
        merge_multimodal(context, [figure, other], [], [])
        self.assertIsNone(figure.caption)
        self.assertIsNone(other.caption)

    def test_signed_and_scientific_metrics(self):
        self.assertEqual(_parse_output_metrics("loss: -1.2e-3 accuracy=.95"), {"loss": -0.0012, "accuracy": 0.95})

    @patch("agents.stage5_executor_validator.subprocess.run")
    def test_process_exit_code_is_checked(self, run):
        run.return_value = CompletedProcess([], 1, "accuracy: 90", "failure")
        output, error, timed_out = _run_docker_container("test")
        self.assertTrue(output)
        self.assertIn("Exit code 1", error)
        self.assertFalse(timed_out)
        run.return_value = CompletedProcess([], 0, "accuracy: 90", "warning")
        self.assertEqual(_run_docker_container("test")[1], "")

    @patch("agents.stage5_executor_validator.subprocess.run")
    def test_timeout_removes_container(self, run):
        run.side_effect = [TimeoutExpired("docker", 1), CompletedProcess([], 0)]
        self.assertTrue(_run_docker_container("test")[2])
        self.assertEqual(run.call_args_list[1].args[0][:3], ["docker", "rm", "-f"])

if __name__ == "__main__":
    unittest.main()
