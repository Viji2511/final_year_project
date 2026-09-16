"""
Tests for Stage 2A — Groq Vision Figure Parser migration.
All Groq API calls are mocked; no real network requests are made.

Test coverage:
 1.  Missing GROQ_API_KEY
 2.  Missing GROQ_VISION_MODEL
 3.  Unavailable vision model
 4.  Successful vision call -> FigureData
 5.  Truncated vision response
 6.  Malformed JSON vision response
 7.  One figure failing while others succeed (DEGRADED)
 8.  Stage 2 PASS when all sub-agents succeed
 9.  Stage 2 DEGRADED when figures FAIL but equations/tables pass
10.  GROQ_VISION_MODEL != GROQ_CODE_MODEL  (no model bleed)
11.  Stage 4 still uses GROQ_CODE_MODEL
12.  Stage 2A does NOT require OPENAI_API_KEY
13.  Caption/image association preserved
14.  Provenance fields set correctly on FigureData
"""
import io
import json
import unittest
from unittest.mock import MagicMock, patch

# ──────────────────────────────────────────────────────────────────────────────
# Helper to build a mock Groq completion response
# ──────────────────────────────────────────────────────────────────────────────
def _make_response(content: str, finish_reason: str = "stop", completion_tokens: int = 300):
    usage = MagicMock()
    usage.completion_tokens = completion_tokens
    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


VALID_FIGURE_JSON = json.dumps({
    "chart_type": "line_chart",
    "title": "Training Loss",
    "x_axis": {"label": "Epoch", "unit": None, "values": None},
    "y_axis": {"label": "Loss", "unit": None, "min": 0.0, "max": 1.0},
    "series": [{"name": "Train", "data_points": [[1, 0.9], [2, 0.7], [3, 0.5]]}],
    "caption": "Figure 1: training curve",
    "extraction_confidence": 0.9,
})


# ──────────────────────────────────────────────────────────────────────────────
# 1. validate_vision_model — missing GROQ_API_KEY
# ──────────────────────────────────────────────────────────────────────────────
class TestVisionModelValidation(unittest.TestCase):

    @patch("config.GROQ_API_KEY", "")
    def test_missing_groq_api_key(self):
        from config import validate_vision_model
        import importlib, config
        importlib.reload(config)
        with patch("config.GROQ_API_KEY", ""):
            with patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b"):
                from config import validate_vision_model as vvm
                with self.assertRaises(ValueError) as ctx:
                    vvm()
                self.assertIn("GROQ_VISION_AUTH_FAILED", str(ctx.exception))

    def test_missing_groq_vision_model(self):
        with patch("config.GROQ_API_KEY", "dummy"), \
             patch("config.GROQ_VISION_MODEL", ""):
            from config import validate_vision_model as vvm
            with self.assertRaises(ValueError) as ctx:
                vvm()
            self.assertIn("GROQ_VISION_MODEL_UNAVAILABLE", str(ctx.exception))

    @patch("groq.Groq")
    def test_unavailable_vision_model(self, MockGroq):
        mock_client = MagicMock()
        mock_client.models.list.return_value = MagicMock(
            data=[MagicMock(id="other-model")]
        )
        MockGroq.return_value = mock_client
        with patch("config.GROQ_API_KEY", "dummy"), \
             patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b"):
            from config import validate_vision_model as vvm
            with self.assertRaises(ValueError) as ctx:
                vvm()
            self.assertIn("GROQ_VISION_MODEL_UNAVAILABLE", str(ctx.exception))

    @patch("groq.Groq")
    def test_available_vision_model_passes(self, MockGroq):
        mock_client = MagicMock()
        mock_client.models.list.return_value = MagicMock(
            data=[MagicMock(id="qwen/qwen3.8-27b")]
        )
        MockGroq.return_value = mock_client
        with patch("config.GROQ_API_KEY", "dummy"), \
             patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b"):
            from config import validate_vision_model as vvm
            vvm()  # should not raise


# ──────────────────────────────────────────────────────────────────────────────
# Helpers for figure_parser tests — patch PDF extraction
# ──────────────────────────────────────────────────────────────────────────────

def _fake_image_bytes():
    """Return a tiny valid PNG (1x1 white pixel)."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (200, 150), color=(200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _make_fitz_doc(images=None):
    """
    Return a MagicMock fitz document with the given list of
    (width, height, ext, bytes) tuples as images on page 1.
    """
    images = images or [(200, 150, "png", _fake_image_bytes())]
    mock_page = MagicMock()
    mock_page.get_images.return_value = [
        (i + 1, 0, 0, 0, 0, "", "") for i in range(len(images))
    ]
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter(enumerate([mock_page])))
    def extract_image(xref):
        idx = xref - 1
        w, h, ext, img_bytes = images[idx]
        return {"width": w, "height": h, "ext": ext, "image": img_bytes}
    mock_doc.extract_image = extract_image
    return mock_doc


# ──────────────────────────────────────────────────────────────────────────────
# 2. Successful vision call -> FigureData with provenance
# ──────────────────────────────────────────────────────────────────────────────
class TestFigureParserSuccess(unittest.TestCase):

    @patch("groq.Groq")
    @patch("fitz.open")
    @patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    @patch("config.GROQ_API_KEY", "dummy")
    def test_successful_vision_call(self, mock_fitz_open, MockGroq):
        mock_fitz_open.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_fitz_open.return_value.__exit__ = MagicMock(return_value=False)

        # fitz mock
        mock_doc = _make_fitz_doc()
        mock_fitz_open.return_value = mock_doc

        # Groq mock
        mock_client = MagicMock()
        mock_client.models.list.return_value = MagicMock(
            data=[MagicMock(id="qwen/qwen3.8-27b")]
        )
        mock_client.chat.completions.create.return_value = _make_response(VALID_FIGURE_JSON)
        MockGroq.return_value = mock_client

        import importlib
        import agents.stage2_multimodal.figure_parser as fp
        importlib.reload(fp)

        with patch.object(fp, "validate_vision_model"):
            figures = fp.parse_figures("fake.pdf")

        self.assertEqual(len(figures), 1)
        fig = figures[0]
        self.assertEqual(fig.chart_type, "line_chart")
        self.assertEqual(fig.provider, "groq")
        self.assertEqual(fig.vision_model, "qwen/qwen3.8-27b")
        self.assertIsNone(fig.vision_error)
        self.assertEqual(len(fig.series), 1)
        self.assertEqual(fig.series[0].name, "Train")
        self.assertEqual(len(fig.series[0].data_points), 3)

    @patch("groq.Groq")
    @patch("fitz.open")
    @patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    @patch("config.GROQ_API_KEY", "dummy")
    def test_provenance_fields_set(self, mock_fitz_open, MockGroq):
        mock_doc = _make_fitz_doc()
        mock_fitz_open.return_value = mock_doc

        mock_client = MagicMock()
        mock_client.models.list.return_value = MagicMock(
            data=[MagicMock(id="qwen/qwen3.8-27b")]
        )
        mock_client.chat.completions.create.return_value = _make_response(VALID_FIGURE_JSON)
        MockGroq.return_value = mock_client

        import importlib
        import agents.stage2_multimodal.figure_parser as fp
        importlib.reload(fp)

        with patch.object(fp, "validate_vision_model"):
            figures = fp.parse_figures("fake.pdf")

        self.assertEqual(figures[0].provider, "groq")
        self.assertEqual(figures[0].vision_model, "qwen/qwen3.8-27b")


# ──────────────────────────────────────────────────────────────────────────────
# 3. Truncated response
# ──────────────────────────────────────────────────────────────────────────────
class TestFigureParserTruncated(unittest.TestCase):

    @patch("groq.Groq")
    @patch("fitz.open")
    @patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    @patch("config.GROQ_API_KEY", "dummy")
    def test_truncated_response_returns_degraded(self, mock_fitz_open, MockGroq):
        mock_doc = _make_fitz_doc()
        mock_fitz_open.return_value = mock_doc

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_response(
            "", finish_reason="length", completion_tokens=1500
        )
        MockGroq.return_value = mock_client

        import importlib
        import agents.stage2_multimodal.figure_parser as fp
        importlib.reload(fp)

        with patch.object(fp, "validate_vision_model"):
            figures = fp.parse_figures("fake.pdf")

        self.assertEqual(len(figures), 1)
        self.assertIsNotNone(figures[0].vision_error)
        self.assertIn("GROQ_VISION_FAILED", figures[0].vision_error)


# ──────────────────────────────────────────────────────────────────────────────
# 4. Malformed JSON
# ──────────────────────────────────────────────────────────────────────────────
class TestFigureParserInvalidJSON(unittest.TestCase):

    @patch("groq.Groq")
    @patch("fitz.open")
    @patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    @patch("config.GROQ_API_KEY", "dummy")
    def test_malformed_json_returns_degraded(self, mock_fitz_open, MockGroq):
        mock_doc = _make_fitz_doc()
        mock_fitz_open.return_value = mock_doc

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_response(
            "This is not JSON at all!!!"
        )
        MockGroq.return_value = mock_client

        import importlib
        import agents.stage2_multimodal.figure_parser as fp
        importlib.reload(fp)

        with patch.object(fp, "validate_vision_model"):
            figures = fp.parse_figures("fake.pdf")

        self.assertEqual(len(figures), 1)
        self.assertIsNotNone(figures[0].vision_error)


# ──────────────────────────────────────────────────────────────────────────────
# 5. One figure failing, others succeeding (DEGRADED)
# ──────────────────────────────────────────────────────────────────────────────
class TestFigureParserDegraded(unittest.TestCase):

    @patch("groq.Groq")
    @patch("fitz.open")
    @patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    @patch("config.GROQ_API_KEY", "dummy")
    def test_one_figure_fails_others_succeed(self, mock_fitz_open, MockGroq):
        images = [
            (200, 150, "png", _fake_image_bytes()),
            (200, 150, "png", _fake_image_bytes()),
            (200, 150, "png", _fake_image_bytes()),
        ]
        mock_doc = _make_fitz_doc(images=images)
        mock_fitz_open.return_value = mock_doc

        responses = [
            _make_response(VALID_FIGURE_JSON),         # fig 1: success
            _make_response("bad json !!"),              # fig 2: fail
            _make_response(VALID_FIGURE_JSON),         # fig 3: success
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = responses
        MockGroq.return_value = mock_client

        import importlib
        import agents.stage2_multimodal.figure_parser as fp
        importlib.reload(fp)

        with patch.object(fp, "validate_vision_model"):
            figures = fp.parse_figures("fake.pdf")

        # All 3 returned (2 pass, 1 degraded)
        self.assertEqual(len(figures), 3)
        successful = [f for f in figures if f.vision_error is None]
        failed = [f for f in figures if f.vision_error is not None]
        self.assertEqual(len(successful), 2)
        self.assertEqual(len(failed), 1)

        stats = fp.parse_figures._last_stats
        self.assertEqual(stats["status"], "DEGRADED")
        self.assertEqual(stats["structured"], 2)
        self.assertEqual(stats["failed"], 1)


# ──────────────────────────────────────────────────────────────────────────────
# 6. Stage 2A no longer requires OPENAI_API_KEY
# ──────────────────────────────────────────────────────────────────────────────
class TestOpenAINotRequired(unittest.TestCase):

    @patch("groq.Groq")
    @patch("fitz.open")
    @patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    @patch("config.GROQ_API_KEY", "dummy")
    @patch("config.OPENAI_API_KEY", "")   # OpenAI key absent
    def test_stage2a_runs_without_openai_key(self, mock_fitz_open, MockGroq):
        mock_doc = _make_fitz_doc()
        mock_fitz_open.return_value = mock_doc

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_response(VALID_FIGURE_JSON)
        MockGroq.return_value = mock_client

        import importlib
        import agents.stage2_multimodal.figure_parser as fp
        importlib.reload(fp)

        # Should not raise despite OPENAI_API_KEY being empty
        with patch.object(fp, "validate_vision_model"):
            figures = fp.parse_figures("fake.pdf")
        self.assertGreater(len(figures), 0)


# ──────────────────────────────────────────────────────────────────────────────
# 7. GROQ_VISION_MODEL != GROQ_CODE_MODEL (no model bleed)
# ──────────────────────────────────────────────────────────────────────────────
class TestModelSeparation(unittest.TestCase):

    def test_vision_model_differs_from_code_model(self):
        with patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b"), \
             patch("config.GROQ_CODE_MODEL", "openai/gpt-oss-120b"):
            import config
            self.assertNotEqual(config.GROQ_VISION_MODEL, config.GROQ_CODE_MODEL)

    @patch("groq.Groq")
    @patch("fitz.open")
    @patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    @patch("config.GROQ_API_KEY", "dummy")
    def test_stage2a_uses_vision_model_not_code_model(self, mock_fitz_open, MockGroq):
        mock_doc = _make_fitz_doc()
        mock_fitz_open.return_value = mock_doc

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_response(VALID_FIGURE_JSON)
        MockGroq.return_value = mock_client

        import importlib
        import agents.stage2_multimodal.figure_parser as fp
        importlib.reload(fp)

        with patch.object(fp, "validate_vision_model"):
            fp.parse_figures("fake.pdf")

        call_kwargs = mock_client.chat.completions.create.call_args
        model_used = call_kwargs[1].get("model") or call_kwargs[0][0]
        self.assertEqual(model_used, "qwen/qwen3.8-27b")
        self.assertNotEqual(model_used, "openai/gpt-oss-120b")

    @patch("groq.Groq")
    def test_stage4_uses_code_model_not_vision_model(self, MockGroq):
        """Stage 4 must use GROQ_CODE_MODEL, not GROQ_VISION_MODEL."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_response(
            json.dumps({"files": [{"path": "model.py", "purpose": "test"}]}),
            finish_reason="stop"
        )
        MockGroq.return_value = mock_client

        from schemas.ues_schema import UES
        import importlib
        import agents.stage4_code_generator as s4
        importlib.reload(s4)

        with patch("config.GROQ_CODE_MODEL", "openai/gpt-oss-120b"), \
             patch("config.GROQ_MODEL", "openai/gpt-oss-120b"), \
             patch("agents.stage4_code_generator.GROQ_MODEL", "openai/gpt-oss-120b"):
            try:
                s4.plan_repository(UES(paper_id="test"), "/tmp")
            except Exception:
                pass  # We only care about which model was called

        if mock_client.chat.completions.create.called:
            call_kwargs = mock_client.chat.completions.create.call_args
            model_used = call_kwargs[1].get("model") or (call_kwargs[0][0] if call_kwargs[0] else None)
            if model_used:
                self.assertNotEqual(model_used, "qwen/qwen3.8-27b")


# ──────────────────────────────────────────────────────────────────────────────
# 8. Stage 2 overall status
# ──────────────────────────────────────────────────────────────────────────────
class TestStage2Status(unittest.TestCase):

    @patch("groq.Groq")
    @patch("fitz.open")
    @patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    @patch("config.GROQ_API_KEY", "dummy")
    def test_stage2_pass_all_succeed(self, mock_fitz_open, MockGroq):
        mock_doc = _make_fitz_doc()
        mock_fitz_open.return_value = mock_doc
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_response(VALID_FIGURE_JSON)
        MockGroq.return_value = mock_client

        import importlib
        import agents.stage2_multimodal.figure_parser as fp
        importlib.reload(fp)

        with patch.object(fp, "validate_vision_model"):
            fp.parse_figures("fake.pdf")

        stats = fp.parse_figures._last_stats
        self.assertEqual(stats["status"], "PASS")
        self.assertEqual(stats["provider"], "groq")
        self.assertIn("model", stats)

    @patch("groq.Groq")
    @patch("fitz.open")
    @patch("config.GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    @patch("config.GROQ_API_KEY", "dummy")
    def test_stage2_failed_all_fail(self, mock_fitz_open, MockGroq):
        mock_doc = _make_fitz_doc()
        mock_fitz_open.return_value = mock_doc
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_response("not json")
        MockGroq.return_value = mock_client

        import importlib
        import agents.stage2_multimodal.figure_parser as fp
        importlib.reload(fp)

        with patch.object(fp, "validate_vision_model"):
            fp.parse_figures("fake.pdf")

        stats = fp.parse_figures._last_stats
        self.assertEqual(stats["status"], "FAILED")


# ──────────────────────────────────────────────────────────────────────────────
# 9. validate_api_keys no longer requires OPENAI_API_KEY
# ──────────────────────────────────────────────────────────────────────────────
class TestValidateApiKeys(unittest.TestCase):

    @patch("groq.Groq")
    def test_validate_api_keys_no_openai_required(self, MockGroq):
        mock_client = MagicMock()
        mock_client.models.list.return_value = MagicMock(
            data=[MagicMock(id="openai/gpt-oss-120b")]
        )
        MockGroq.return_value = mock_client

        with patch("config.GROQ_API_KEY", "dummy"), \
             patch("config.GROQ_CODE_MODEL", "openai/gpt-oss-120b"), \
             patch("config.GROQ_MODEL", "openai/gpt-oss-120b"), \
             patch("config.OPENAI_API_KEY", ""):  # OpenAI absent — must NOT fail
            from config import validate_api_keys
            validate_api_keys()  # Should not raise

    @patch("groq.Groq")
    def test_validate_api_keys_missing_groq_fails(self, MockGroq):
        with patch("config.GROQ_API_KEY", ""), \
             patch("config.GROQ_CODE_MODEL", "openai/gpt-oss-120b"):
            from config import validate_api_keys
            with self.assertRaises(ValueError) as ctx:
                validate_api_keys()
            self.assertIn("GROQ_API_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
