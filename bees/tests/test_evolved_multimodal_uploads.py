"""Regression tests for multipart bytes, base64 attachments and response serialization."""
import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bees.config import BeeConfig
from enxame_evolved.kernel import EnxameKernel
from enxame_evolved.multimodal import MultimodalProcessor, ProcessedFile


@pytest.mark.asyncio
async def test_raw_upload_bytes_are_not_base64_decoded(tmp_path):
    processor = MultimodalProcessor(data_dir=tmp_path, models=[])
    result = await processor._process_attachment({
        "filename": "notes.txt", "content": b"Hello bytes",
        "content_type": "text/plain",
    })
    assert result.content == "Hello bytes"
    assert result.size_bytes == len(b"Hello bytes")


@pytest.mark.asyncio
async def test_chat_base64_and_filename_sanitization(tmp_path):
    processor = MultimodalProcessor(data_dir=tmp_path, models=[])
    result = await processor._process_attachment({
        "filename": "../notes.txt",
        "content": base64.b64encode(b"Hello text").decode(),
        "content_type": "text/plain",
    })
    assert result.filename == "notes.txt"
    assert result.content == "Hello text"
    assert not (tmp_path / "notes.txt").exists()


@pytest.mark.asyncio
async def test_invalid_base64_is_not_silently_replaced_with_empty_bytes(tmp_path):
    processor = MultimodalProcessor(data_dir=tmp_path, models=[])
    with pytest.raises(ValueError, match="base64"):
        await processor._process_attachment({
            "filename": "bad.txt", "content": "@not-base64!",
            "content_type": "text/plain",
        })


@pytest.mark.asyncio
async def test_kernel_processes_attachment_once_and_serializes_result(tmp_path):
    kernel = EnxameKernel(BeeConfig(data_dir=tmp_path))
    kernel._analyze_intent = AsyncMock(return_value={"task": "describe", "task_type": "document"})
    kernel._profiles = SimpleNamespace(select_or_create_profile=AsyncMock(
        return_value=SimpleNamespace(profile_id="generalist")))
    item = ProcessedFile(file_id="abc", filename="test.txt", mime_type="text/plain",
                         size_bytes=3, content="abc")
    kernel._multimodal = SimpleNamespace(process_attachments=AsyncMock(
        return_value={"files": [item], "ocr_text": "abc"}))
    kernel._orchestrator = SimpleNamespace(execute_task=AsyncMock(
        return_value={"answer": "ok", "confidence": 1.0}))
    result = await kernel.process_chat("describe", {"attachments": [{"filename": "test.txt", "content": b"abc"}]})
    assert json.loads(json.dumps(result))["metadata"]["multimodal"]["files"][0]["filename"] == "test.txt"
    assert kernel._multimodal.process_attachments.await_count == 1
    passed_context = kernel._orchestrator.execute_task.await_args.kwargs["context"]
    assert "attachments" not in passed_context
    assert passed_context["multimodal_processed"] is True
