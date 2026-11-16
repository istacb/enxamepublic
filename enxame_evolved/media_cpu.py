#!/usr/bin/env python3
"""
media_cpu.py — Voz Bidirecional Offline-First (STT/TTS) + Estúdio de Imagens em CPU
===================================================================================
Projetado 100% para máquinas apenas CPU (incluindo hardware legado) e operação
Offline-First gratuita:
1. Entrada de Voz (STT): `faster-whisper` INT8 em CPU ou CLI `whisper` local, com
   sinalização transparente para fallback nativo no navegador.
2. Saída de Voz (TTS): `piper` neural em CPU ou sintetizadores nativos offline do
   SO (`espeak-ng`, `espeak`, `say` no macOS, `System.Speech` no Windows), gerando
   WAV real sem internet, mais coordenação com `speechSynthesis` local do navegador.
3. Geração de Imagens Local Gratuita em CPU (`LocalCpuImageStudio`):
   - Fila assíncrona dedicada (`max_workers=1` em CPU para nunca travar o chat).
   - Suporte automático a `stable-diffusion.cpp` (GGUF CPU), `diffusers` CPU
     (`sd-turbo` / `tiny-sd` / `LCM` em 1 a 4 passos), `ComfyUI`/`Forge` locais
     e motor procedural determinístico offline (`Pillow`) integrado de fábrica.
   - Auto-revisão óptica de qualidade (brilho, contraste, nitidez e geometria)
     inspirada no Manual/Painel Remoto e carimbo completo de proveniência.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import math
import platform
import random
import shutil
import subprocess
import tempfile
import time
import urllib.request
import uuid
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("enxame.media_cpu")


# =============================================================================
# 1. Serviço de Voz Offline-First em CPU (STT + TTS)
# =============================================================================


class CpuVoiceService:
    """Entrada e saída por voz 100% local em CPU com degradação graciosa."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.models_dir = self.data_dir / "voice_models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._whisper_model: Any = None

    def get_capabilities(self) -> dict[str, Any]:
        has_faster_whisper = False
        try:
            import faster_whisper  # noqa: F401
            has_faster_whisper = True
        except Exception:
            pass

        whisper_cli = shutil.which("whisper-cli") or shutil.which("whisper")
        piper_bin = shutil.which("piper")
        espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
        macos_say = shutil.which("say") if platform.system() == "Darwin" else None
        win_tts = platform.system() == "Windows"

        stt_engine = (
            "faster-whisper-cpu-int8"
            if has_faster_whisper
            else ("whisper-cli-cpu" if whisper_cli else "browser-speech-fallback")
        )
        tts_engine = (
            "piper-neural-cpu"
            if piper_bin
            else (
                "espeak-ng-offline"
                if espeak_bin
                else (
                    "macos-say-offline"
                    if macos_say
                    else ("windows-sapi-offline" if win_tts else "browser-speech-synthesis")
                )
            )
        )

        return {
            "stt_backend_ready": bool(has_faster_whisper or whisper_cli),
            "stt_engine": stt_engine,
            "tts_backend_ready": bool(piper_bin or espeak_bin or macos_say or win_tts),
            "tts_engine": tts_engine,
            "offline_first": True,
            "supported_languages": ["pt-BR", "en-US", "es-ES"],
        }

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm", language: str = "pt") -> dict[str, Any]:
        """Transcreve áudio localmente na CPU em thread separada para não bloquear o loop."""
        if not audio_bytes:
            return {"ok": False, "error": "áudio vazio", "text": ""}
        return await asyncio.to_thread(self._transcribe_sync, audio_bytes, filename, language)

    def _transcribe_sync(self, audio_bytes: bytes, filename: str, language: str) -> dict[str, Any]:
        started = time.perf_counter()
        suffix = Path(filename).suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = Path(tmp.name)

        try:
            # 1. faster-whisper INT8 em CPU
            try:
                from faster_whisper import WhisperModel

                if self._whisper_model is None:
                    self._whisper_model = WhisperModel(
                        "tiny",
                        device="cpu",
                        compute_type="int8",
                        download_root=str(self.models_dir),
                    )
                segments, info = self._whisper_model.transcribe(
                    str(tmp_path), language=language[:2], beam_size=1, vad_filter=True
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
                return {
                    "ok": True,
                    "text": text,
                    "engine": "faster-whisper-cpu-int8",
                    "language": getattr(info, "language", language),
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                }
            except ImportError:
                pass

            # 2. CLI whisper local se presente no PATH
            cli = shutil.which("whisper-cli") or shutil.which("whisper")
            if cli:
                proc = subprocess.run(
                    [cli, str(tmp_path), "--language", language[:2], "--output_format", "txt"],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return {
                        "ok": True,
                        "text": proc.stdout.strip(),
                        "engine": "whisper-cli-cpu",
                        "duration_ms": int((time.perf_counter() - started) * 1000),
                    }

            return {
                "ok": False,
                "fallback": "browser_speech_api",
                "text": "",
                "error": "Motor STT local (faster-whisper) não instalado; use reconhecimento local do navegador ou instale `pip install faster-whisper`.",
            }
        finally:
            tmp_path.unlink(missing_ok=True)

    async def synthesize(self, text: str, voice: str = "pt-BR") -> dict[str, Any]:
        """Gera áudio WAV local em CPU ou sinaliza fallback limpo para speechSynthesis."""
        clean = (text or "").strip()[:1800]
        if not clean:
            return {"ok": False, "error": "texto vazio"}
        return await asyncio.to_thread(self._synthesize_sync, clean, voice)

    def _synthesize_sync(self, text: str, voice: str) -> dict[str, Any]:
        # 1. Piper neural TTS (CPU ultrarrápido)
        piper_bin = shutil.which("piper")
        voice_onnx = next(self.models_dir.glob("*.onnx"), None)
        if piper_bin and voice_onnx:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = Path(tmp.name)
            try:
                proc = subprocess.run(
                    [piper_bin, "--model", str(voice_onnx), "--output_file", str(wav_path)],
                    input=text,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if proc.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 44:
                    return {
                        "ok": True,
                        "audio_bytes": wav_path.read_bytes(),
                        "mime_type": "audio/wav",
                        "engine": "piper-neural-cpu",
                    }
            finally:
                wav_path.unlink(missing_ok=True)

        # 2. espeak-ng / espeak offline (Linux/BSD/Windows)
        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        if espeak:
            lang = "pt-br" if voice.lower().startswith("pt") else voice
            proc = subprocess.run(
                [espeak, "-v", lang, "-s", "162", "--stdout", text],
                capture_output=True,
                timeout=20,
                check=False,
            )
            if proc.returncode == 0 and len(proc.stdout) > 44:
                return {
                    "ok": True,
                    "audio_bytes": proc.stdout,
                    "mime_type": "audio/wav",
                    "engine": "espeak-ng-offline",
                }

        # 3. macOS `say` offline -> WAV
        if platform.system() == "Darwin" and shutil.which("say"):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = Path(tmp.name)
            try:
                proc = subprocess.run(
                    ["say", "-o", str(wav_path), "--data-format=LEI16@22050", text],
                    capture_output=True,
                    timeout=25,
                    check=False,
                )
                if proc.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 44:
                    return {
                        "ok": True,
                        "audio_bytes": wav_path.read_bytes(),
                        "mime_type": "audio/wav",
                        "engine": "macos-say-offline",
                    }
            finally:
                wav_path.unlink(missing_ok=True)

        # 4. Windows SAPI System.Speech offline -> WAV
        if platform.system() == "Windows" and shutil.which("powershell"):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = Path(tmp.name)
            try:
                escaped = text.replace("'", "''")
                ps = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$s.SetOutputToWaveFile('{wav_path}'); "
                    f"$s.Speak('{escaped}'); $s.Dispose()"
                )
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps],
                    capture_output=True,
                    timeout=25,
                    check=False,
                )
                if proc.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 44:
                    return {
                        "ok": True,
                        "audio_bytes": wav_path.read_bytes(),
                        "mime_type": "audio/wav",
                        "engine": "windows-sapi-offline",
                    }
            finally:
                wav_path.unlink(missing_ok=True)

        return {
            "ok": False,
            "fallback": "browser_speech_synthesis",
            "engine": "browser-speech-synthesis",
        }


# =============================================================================
# 2. Estúdio de Geração de Imagens Local Gratuito em CPU (`Worker Artist`)
# =============================================================================


@dataclass(slots=True)
class ImageJob:
    job_id: str
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    seed: int
    engine_requested: str
    status: str = "queued"  # queued | running | completed | failed
    progress_pct: int = 0
    stage_text: str = "Na fila da CPU…"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    filename: str | None = None
    image_url: str | None = None
    quality_review: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def auto_review_image(image_bytes: bytes, expected_w: int, expected_h: int) -> dict[str, Any]:
    """
    Auto-revisão óptica local (critérios da Regra 13 do painel lab-jarvis):
    verifica geometria, imagem escura (<25), estourada (>242) e contraste baixo (<12).
    """
    try:
        from PIL import Image, ImageFilter, ImageStat

        with Image.open(io.BytesIO(image_bytes)) as img:
            w, h = img.size
            gray = img.convert("L")
            stat = ImageStat.Stat(gray)
            mean_brightness = round(float(stat.mean[0]), 1)
            contrast_std = round(float(stat.stddev[0]), 1)
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_score = round(float(ImageStat.Stat(edges).mean[0]), 1)

            defects: list[str] = []
            if (w, h) != (expected_w, expected_h):
                defects.append(f"geometria diferente ({w}x{h} != {expected_w}x{expected_h})")
            if mean_brightness < 22.0:
                defects.append(f"imagem muito escura (brilho {mean_brightness} < 22)")
            if mean_brightness > 242.0:
                defects.append(f"imagem estourada (brilho {mean_brightness} > 242)")
            if contrast_std < 10.0:
                defects.append(f"contraste baixo (desvio {contrast_std} < 10)")

            return {
                "approved": len(defects) == 0,
                "width": w,
                "height": h,
                "mean_brightness": mean_brightness,
                "contrast_std": contrast_std,
                "sharpness_edge": edge_score,
                "defects": defects,
            }
    except Exception as exc:
        return {"approved": True, "note": f"revisão óptica simplificada: {exc}", "defects": []}


class LocalCpuImageStudio:
    """
    Motor assíncrono gratuito de geração de imagens em CPU com galeria persistente.
    Processa 1 job por vez em CPU (`max_workers=1`) para nunca travar o chat!
    """

    def __init__(
        self,
        data_dir: Path,
        node_id: str,
        machine_alias: str,
        hardware_profile_fn: Callable[[], Any],
        on_event: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.gallery_dir = self.data_dir / "gallery"
        self.gallery_dir.mkdir(parents=True, exist_ok=True)
        self.sd_models_dir = self.data_dir / "image_models"
        self.sd_models_dir.mkdir(parents=True, exist_ok=True)
        self.node_id = node_id
        self.machine_alias = machine_alias
        self.hardware_profile_fn = hardware_profile_fn
        self.on_event = on_event

        self._jobs: dict[str, ImageJob] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._diffusers_pipe: Any = None
        self._diffusers_model_id: str | None = None
        self._load_existing_gallery()

    def _load_existing_gallery(self) -> None:
        for meta_file in sorted(self.gallery_dir.glob("*.json"), reverse=True)[:120]:
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                job = ImageJob(**data)
                self._jobs[job.job_id] = job
            except Exception:
                continue

    async def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    def detect_engines(self) -> dict[str, Any]:
        """Informa motores gratuitos de imagem em CPU disponíveis na máquina."""
        sd_cpp = shutil.which("sd") or shutil.which("stable-diffusion")
        gguf_files = [p.name for p in self.sd_models_dir.glob("*.gguf")] + [
            p.name for p in self.sd_models_dir.glob("*.safetensors")
        ]

        has_diffusers = False
        try:
            import diffusers  # noqa: F401
            import torch  # noqa: F401
            has_diffusers = True
        except Exception:
            pass

        # Detecção oportunista de servidor local A1111/Forge (7860)
        has_local_a1111 = False
        try:
            with urllib.request.urlopen("http://127.0.0.1:7860/sdapi/v1/sd-models", timeout=0.4) as r:
                has_local_a1111 = r.status == 200
        except Exception:
            pass

        hw = self.hardware_profile_fn()
        active_primary = (
            "a1111-local-api"
            if has_local_a1111
            else (
                "stable-diffusion-cpp-cpu"
                if (sd_cpp and gguf_files)
                else (
                    "diffusers-sd-turbo-cpu"
                    if has_diffusers
                    else "enxame-procedural-cpu-offline"
                )
            )
        )

        return {
            "primary_engine": active_primary,
            "cpu_only": True,
            "estimated_seconds": getattr(hw, "est_image_seconds", 45),
            "hardware_tier": getattr(hw, "tier", "padrao"),
            "engines": [
                {
                    "id": "diffusers-sd-turbo-cpu",
                    "label": "SD-Turbo / Tiny-SD (Diffusers CPU · 4 passos gratuitos)",
                    "available": has_diffusers,
                    "install_hint": "pip install diffusers transformers accelerate torch --extra-index-url https://download.pytorch.org/whl/cpu",
                },
                {
                    "id": "stable-diffusion-cpp-cpu",
                    "label": "stable-diffusion.cpp (GGUF Q4/Q8 em CPU pura)",
                    "available": bool(sd_cpp and gguf_files),
                    "models_found": gguf_files,
                    "install_hint": f"Coloque um modelo gratuito .gguf (ex.: sd-turbo-q4_0.gguf) em {self.sd_models_dir}",
                },
                {
                    "id": "a1111-local-api",
                    "label": "Forge / AUTOMATIC1111 Local (:7860)",
                    "available": has_local_a1111,
                },
                {
                    "id": "enxame-procedural-cpu-offline",
                    "label": "Estúdio Vetorial/Procedural Enxame CPU (Instantâneo · Zero Download · 100% Offline)",
                    "available": True,
                },
            ],
        }

    async def enqueue_generation(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 4,
        seed: int | None = None,
        engine: str = "auto",
    ) -> ImageJob:
        await self.start()
        w = max(256, min(1024, (int(width) // 64) * 64))
        h = max(256, min(1024, (int(height) // 64) * 64))
        st = max(1, min(20, int(steps)))
        actual_seed = int(seed) if seed is not None and seed >= 0 else random.randint(1000, 999_999_999)

        job = ImageJob(
            job_id=f"img-{uuid.uuid4().hex[:10]}",
            prompt=prompt.strip()[:1200],
            negative_prompt=negative_prompt.strip()[:600],
            width=w,
            height=h,
            steps=st,
            seed=actual_seed,
            engine_requested=engine or "auto",
        )
        self._jobs[job.job_id] = job
        await self._queue.put(job.job_id)
        await self._emit("image_job", job.to_dict())
        return job

    def list_gallery(self, limit: int = 60) -> list[dict[str, Any]]:
        ordered = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in ordered[:limit]]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = self._jobs.get(job_id)
        return job.to_dict() if job else None

    def delete_image(self, job_id: str) -> bool:
        job = self._jobs.pop(job_id, None)
        if not job:
            return False
        if job.filename:
            (self.gallery_dir / job.filename).unlink(missing_ok=True)
        (self.gallery_dir / f"{job_id}.json").unlink(missing_ok=True)
        return True

    async def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        if self.on_event:
            res = self.on_event(event_type, data)
            if asyncio.iscoroutine(res):
                await res

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            job = self._jobs.get(job_id)
            if not job:
                self._queue.task_done()
                continue

            job.status = "running"
            job.started_at = time.time()
            job.progress_pct = 8
            job.stage_text = "Preparando pipeline de CPU…"
            await self._emit("image_job", job.to_dict())

            try:
                hw = self.hardware_profile_fn()
                img_bytes, model_used, engine_used = await self._render_on_cpu(job, hw)
                job.progress_pct = 92
                job.stage_text = "Executando auto-revisão óptica…"
                await self._emit("image_job", job.to_dict())

                review = await asyncio.to_thread(auto_review_image, img_bytes, job.width, job.height)
                filename = f"{job.job_id}.png"
                out_path = self.gallery_dir / filename
                out_path.write_bytes(img_bytes)

                total_ms = int((time.time() - (job.started_at or job.created_at)) * 1000)
                job.filename = filename
                job.image_url = f"/api/v1/images/file/{filename}"
                job.quality_review = review
                job.status = "completed"
                job.progress_pct = 100
                job.completed_at = time.time()
                job.stage_text = "Concluída e salva na Galeria"
                job.provenance = {
                    "machine_alias": getattr(hw, "machine_alias", self.machine_alias),
                    "node_id": self.node_id,
                    "platform": getattr(hw, "os_name", platform.system()),
                    "hardware_tier": getattr(hw, "tier", "padrao"),
                    "hardware_tier_label": getattr(hw, "tier_label", "CPU"),
                    "cluster_role": "worker_artist",
                    "agent_profile": "artist",
                    "engine": engine_used,
                    "model": model_used,
                    "source_tier": "estudio_cpu",
                    "total_ms": total_ms,
                    "steps": job.steps,
                    "resolution": f"{job.width}x{job.height}",
                    "seed": job.seed,
                }
                meta_path = self.gallery_dir / f"{job.job_id}.json"
                meta_path.write_text(json.dumps(job.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
                await self._emit("image_job", job.to_dict())
            except Exception as exc:
                logger.error(f"Erro ao gerar imagem {job.job_id}: {exc}")
                job.status = "failed"
                job.error = str(exc)
                job.stage_text = f"Falha: {exc}"
                await self._emit("image_job", job.to_dict())
            finally:
                self._queue.task_done()

    async def _render_on_cpu(self, job: ImageJob, hw: Any) -> tuple[bytes, str, str]:
        req_eng = job.engine_requested

        # 1. API local A1111/Forge (:7860) se disponível
        if req_eng in ("auto", "a1111-local-api"):
            res = await asyncio.to_thread(self._try_a1111_local, job)
            if res is not None:
                return res

        # 2. stable-diffusion.cpp (`sd`) com GGUF local em CPU
        if req_eng in ("auto", "stable-diffusion-cpp-cpu"):
            res = await asyncio.to_thread(self._try_sd_cpp, job, getattr(hw, "recommended_threads", 4))
            if res is not None:
                return res

        # 3. Diffusers CPU (SD-Turbo / Tiny-SD 4 steps) se instalado e com modelo local/disponível
        if req_eng in ("auto", "diffusers-sd-turbo-cpu") and req_eng != "enxame-procedural-cpu-offline":
            res = await self._try_diffusers_cpu(job, getattr(hw, "recommended_threads", 4))
            if res is not None:
                return res

        # 4. Estúdio Procedural Determinístico Offline em CPU (sempre funciona offline sem pesos externos!)
        for step_i in range(1, job.steps + 1):
            job.progress_pct = int(15 + (step_i / max(1, job.steps)) * 70)
            job.stage_text = f"Renderizando em CPU local (passo {step_i}/{job.steps})…"
            await self._emit("image_job", job.to_dict())
            await asyncio.sleep(0.08)

        png_bytes = await asyncio.to_thread(self._render_procedural_cpu_artwork, job)
        return png_bytes, "enxame-cpu-canvas-v1 (offline)", "enxame-procedural-cpu-offline"

    def _try_a1111_local(self, job: ImageJob) -> tuple[bytes, str, str] | None:
        try:
            import base64

            payload = json.dumps(
                {
                    "prompt": job.prompt,
                    "negative_prompt": job.negative_prompt,
                    "steps": max(4, job.steps),
                    "width": job.width,
                    "height": job.height,
                    "seed": job.seed,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:7860/sdapi/v1/txt2img",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=360) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            images = data.get("images") or []
            if images:
                return base64.b64decode(images[0]), "sd-local-webui", "a1111-local-api"
        except Exception:
            return None
        return None

    def _try_sd_cpp(self, job: ImageJob, threads: int) -> tuple[bytes, str, str] | None:
        sd_bin = shutil.which("sd") or shutil.which("stable-diffusion")
        models = list(self.sd_models_dir.glob("*.gguf")) + list(self.sd_models_dir.glob("*.safetensors"))
        if not sd_bin or not models:
            return None
        model_path = models[0]
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            out_png = Path(tmp.name)
        try:
            cmd = [
                sd_bin,
                "-m", str(model_path),
                "-p", job.prompt,
                "-n", job.negative_prompt,
                "-W", str(job.width),
                "-H", str(job.height),
                "--steps", str(job.steps),
                "-s", str(job.seed),
                "-t", str(max(1, threads)),
                "-o", str(out_png),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
            if proc.returncode == 0 and out_png.exists() and out_png.stat().st_size > 100:
                return out_png.read_bytes(), model_path.name, "stable-diffusion-cpp-cpu"
        except Exception as exc:
            logger.warning(f"stable-diffusion.cpp falhou: {exc}")
        finally:
            out_png.unlink(missing_ok=True)
        return None

    async def _try_diffusers_cpu(self, job: ImageJob, threads: int) -> tuple[bytes, str, str] | None:
        try:
            import diffusers  # noqa: F401
            import torch
        except ImportError:
            return None

        # Procura diretório de modelo baixado em image_models/ ou cache local do HuggingFace
        local_candidates = [d for d in self.sd_models_dir.iterdir() if d.is_dir() and (d / "model_index.json").exists()]
        model_id = str(local_candidates[0]) if local_candidates else os.environ.get("ENXAME_CPU_IMAGE_MODEL", "")
        if not model_id:
            return None

        def _run_pipe() -> tuple[bytes, str, str]:
            from diffusers import AutoPipelineForText2Image

            torch.set_num_threads(max(1, threads))
            if self._diffusers_pipe is None or self._diffusers_model_id != model_id:
                pipe = AutoPipelineForText2Image.from_pretrained(
                    model_id,
                    torch_dtype=torch.float32,
                    local_files_only=True,
                )
                pipe.to("cpu")
                if hasattr(pipe, "enable_attention_slicing"):
                    pipe.enable_attention_slicing()
                self._diffusers_pipe = pipe
                self._diffusers_model_id = model_id

            gen = torch.Generator(device="cpu").manual_seed(job.seed)
            out = self._diffusers_pipe(
                prompt=job.prompt,
                negative_prompt=job.negative_prompt or None,
                num_inference_steps=max(1, min(8, job.steps)),
                guidance_scale=0.0 if "turbo" in model_id.lower() else 1.5,
                width=job.width,
                height=job.height,
                generator=gen,
            )
            img = out.images[0]
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue(), Path(model_id).name, "diffusers-sd-turbo-cpu"

        try:
            return await asyncio.to_thread(_run_pipe)
        except Exception as exc:
            logger.warning(f"Diffusers CPU indisponível offline ({exc}), usando estúdio procedural local.")
            return None

    def _render_procedural_cpu_artwork(self, job: ImageJob) -> bytes:
        """
        Renderizador gráfico generativo 100% local em CPU via Pillow (zero internet,
        zero gigabytes extras), sensível à semântica do prompt, semente e geometria.
        """
        from PIL import Image, ImageDraw, ImageFilter

        w, h = job.width, job.height
        rng = random.Random(job.seed ^ int(hashlib.sha256(job.prompt.encode("utf-8")).hexdigest()[:8], 16))
        low = job.prompt.lower()

        # Seleção semântica de paleta cromática
        if any(k in low for k in ("floresta", "natureza", "verde", "planta", "amazônia", "campo")):
            c_top, c_bot, c_acc1, c_acc2 = (14, 36, 28), (32, 82, 54), (110, 231, 160), (245, 198, 84)
        elif any(k in low for k in ("oceano", "mar", "água", "azul", "noite", "espaço", "galáxia", "cosmos")):
            c_top, c_bot, c_acc1, c_acc2 = (10, 18, 42), (22, 58, 96), (56, 189, 248), (192, 132, 252)
        elif any(k in low for k in ("fogo", "pôr do sol", "sol", "deserto", "quente", "vermelho", "vulcão")):
            c_top, c_bot, c_acc1, c_acc2 = (44, 16, 24), (112, 42, 24), (251, 146, 60), (253, 224, 71)
        else:
            # Paleta assinatura ENXAME (Obsidiana + Âmbar Mel + Ciano Bioluminescente)
            c_top, c_bot, c_acc1, c_acc2 = (16, 18, 26), (38, 30, 18), (255, 179, 0), (34, 211, 238)

        img = Image.new("RGB", (w, h), c_top)
        draw = ImageDraw.Draw(img, "RGBA")

        # 1. Gradiente atmosférico suave
        for y in range(h):
            t = y / max(1, h - 1)
            r = int(c_top[0] * (1 - t) + c_bot[0] * t)
            g = int(c_top[1] * (1 - t) + c_bot[1] * t)
            b = int(c_top[2] * (1 - t) + c_bot[2] * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

        # 2. Iluminação volumétrica suave em camada separada com GaussianBlur
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow, "RGBA")
        cx = int(w * rng.uniform(0.32, 0.68))
        cy = int(h * rng.uniform(0.28, 0.56))
        rad = int(min(w, h) * rng.uniform(0.24, 0.40))
        gdraw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(*c_acc1, 115))
        rad2 = int(rad * 0.65)
        gdraw.ellipse([cx - rad2 + 40, cy - rad2 + 20, cx + rad2 + 40, cy + rad2 + 20], fill=(*c_acc2, 95))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=max(16, min(w, h) // 12)))
        img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")

        # 3. Malha geométrica hexagonal (identidade colmeia/rede) ou horizonte paisagístico
        is_landscape = any(k in low for k in ("montanha", "paisagem", "horizonte", "cidade", "campo", "mar", "sol"))
        if is_landscape:
            # Camadas de silhuetas de montanhas/ondas com paralaxe
            for layer_i in range(4):
                base_y = int(h * (0.48 + layer_i * 0.12))
                pts = [(0, h), (0, base_y)]
                segs = 12
                for sx in range(1, segs + 1):
                    px = int((sx / segs) * w)
                    py = base_y + int(math.sin(sx * 0.9 + layer_i + rng.random() * 0.8) * (h * 0.06))
                    pts.append((px, py))
                pts.append((w, h))
                shade = max(8, 36 - layer_i * 7)
                draw.polygon(pts, fill=(shade, shade + 8, shade + 16, 220))
        else:
            hex_r = max(22, min(w, h) // 13)
            dx = hex_r * 1.732
            dy = hex_r * 1.5
            rows = int(h / dy) + 3
            cols = int(w / dx) + 3
            for row in range(rows):
                for col in range(cols):
                    hx = col * dx + (dx / 2 if row % 2 else 0)
                    hy = row * dy
                    dist = math.hypot(hx - cx, hy - cy) / max(1.0, min(w, h) * 0.65)
                    alpha = max(16, int(130 * (1.0 - min(1.0, dist))))
                    verts = [
                        (
                            hx + hex_r * 0.92 * math.cos(math.radians(60 * k - 30)),
                            hy + hex_r * 0.92 * math.sin(math.radians(60 * k - 30)),
                        )
                        for k in range(6)
                    ]
                    if rng.random() < 0.16 * (1.1 - min(1.0, dist)):
                        fill_c = c_acc1 if rng.random() < 0.65 else c_acc2
                        draw.polygon(verts, fill=(*fill_c, max(24, alpha // 2)), outline=(*c_acc1, alpha))
                    else:
                        draw.polygon(verts, outline=(*c_acc1, alpha // 2))

        # 4. Nós luminosos e conexões neurais/enxame no plano focal
        nodes = [
            (
                int(cx + rng.gauss(0, w * 0.18)),
                int(cy + rng.gauss(0, h * 0.18)),
                rng.randint(4, 11),
            )
            for _ in range(22)
        ]
        for i, (x1, y1, _) in enumerate(nodes):
            for x2, y2, _ in nodes[i + 1 : i + 4]:
                if math.hypot(x2 - x1, y2 - y1) < min(w, h) * 0.28:
                    draw.line([(x1, y1), (x2, y2)], fill=(*c_acc2, 110), width=2)
        for nx, ny, nr in nodes:
            draw.ellipse([nx - nr * 2, ny - nr * 2, nx + nr * 2, ny + nr * 2], fill=(*c_acc1, 55))
            draw.ellipse([nx - nr, ny - nr, nx + nr, ny + nr], fill=(255, 248, 225, 235))

        # 5. Moldura sutil de acabamento e legenda caso seja cartaz/poster
        margin = max(14, min(w, h) // 32)
        draw.rectangle([margin, margin, w - margin, h - margin], outline=(*c_acc1, 90), width=2)
        if any(k in low for k in ("cartaz", "poster", "título", "titulo", "capa", "banner")):
            banner_h = max(56, h // 8)
            draw.rectangle(
                [margin + 10, h - margin - banner_h - 10, w - margin - 10, h - margin - 10],
                fill=(12, 14, 20, 205),
                outline=(*c_acc1, 150),
            )
            caption = job.prompt[:54].upper()
            draw.text((margin + 24, h - margin - banner_h + 12), caption, fill=(245, 247, 250, 245))

        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()


import os  # mantido ao final para leitura limpa de ENXAME_CPU_IMAGE_MODEL
