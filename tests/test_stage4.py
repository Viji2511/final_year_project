import unittest
from unittest.mock import patch, MagicMock
from api.main import app
from fastapi.testclient import TestClient
from schemas.ues_schema import UES
from agents.stage4_code_generator import (
    GenerationTruncatedError,
    validate_generated_file,
    build_codegen_context,
    plan_repository,
    generate_file,
    generate_code
)
import tempfile
import os

class TestStage4(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("config.GROQ_API_KEY", "")
    def test_missing_groq_api_key(self):
        response = self.client.post("/run", params={"paper_id": "test_missing_key"}, files={"file": ("test.pdf", b"%PDF-")})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Missing API keys in .env: GROQ_API_KEY", response.json()["detail"])

    @patch("config.GROQ_MODEL", "")
    @patch("config.GROQ_API_KEY", "dummy")
    def test_missing_groq_model(self):
        response = self.client.post("/run", params={"paper_id": "test_missing_model"}, files={"file": ("test.pdf", b"%PDF-")})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Missing GROQ_MODEL in .env", response.json()["detail"])

    @patch("config.GROQ_MODEL", "invalid-model")
    @patch("config.GROQ_API_KEY", "dummy")
    @patch("groq.Groq")
    def test_invalid_model(self, mock_groq):
        mock_client = MagicMock()
        mock_client.models.list.return_value = MagicMock(data=[MagicMock(id="valid-model")])
        mock_groq.return_value = mock_client
        
        response = self.client.post("/run", params={"paper_id": "test_invalid_model"}, files={"file": ("test.pdf", b"%PDF-")})
        self.assertEqual(response.status_code, 503)
        self.assertIn("is not available", response.json()["detail"])

    @patch("api.main.run_pipeline")
    @patch("api.main.validate_api_keys")
    def test_frontend_receives_clean_error(self, mock_validate, mock_pipeline):
        mock_pipeline.side_effect = ValueError("Groq API Error: model_not_found")
        response = self.client.post("/run", params={"paper_id": "test_clean_error"}, files={"file": ("test.pdf", b"%PDF-")})
        self.assertEqual(response.status_code, 202)
        
        result = self.client.get("/result/test_clean_error").json()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["error_code"], "MODEL_NOT_FOUND")

    @patch("api.main.run_pipeline")
    @patch("api.main.validate_api_keys")
    def test_frontend_receives_truncation_error(self, mock_validate, mock_pipeline):
        mock_pipeline.side_effect = ValueError("Groq API Error: GENERATION_TRUNCATED|model.py|4000")
        response = self.client.post("/run", params={"paper_id": "test_trunc"}, files={"file": ("test.pdf", b"%PDF-")})
        self.assertEqual(response.status_code, 202)
        
        result = self.client.get("/result/test_trunc").json()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["error_code"], "GENERATION_TRUNCATED")
        self.assertEqual(result["error"]["filename"], "model.py")

    def test_validate_generated_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"def foo():\n  return 1")
            path = f.name
        self.assertEqual(validate_generated_file(path, "def foo():\n  return 1"), "")
        
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"def foo() return 1")
            path2 = f.name
        self.assertIn("SyntaxError", validate_generated_file(path2, "def foo() return 1"))
        
        os.remove(path)
        os.remove(path2)

    def test_build_codegen_context(self):
        ues = UES(paper_id="test")
        ctx = build_codegen_context(ues)
        self.assertIn("Task: None", ctx)
        self.assertIn("Dataset: None", ctx)

    @patch("agents.stage4_code_generator.Groq")
    def test_plan_repository_truncation(self, mock_groq):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(finish_reason="length")],
            usage=MagicMock(completion_tokens=1000)
        )
        mock_groq.return_value = mock_client
        
        with self.assertRaises(GenerationTruncatedError):
            plan_repository(UES(paper_id="test"), "/tmp")

    @patch("agents.stage4_code_generator.Groq")
    def test_generate_file_truncation(self, mock_groq):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(finish_reason="length")],
            usage=MagicMock(completion_tokens=4000)
        )
        mock_groq.return_value = mock_client
        
        with self.assertRaises(GenerationTruncatedError):
            generate_file(UES(paper_id="test"), {}, {"path": "model.py"}, "/tmp")

if __name__ == "__main__":
    unittest.main()
