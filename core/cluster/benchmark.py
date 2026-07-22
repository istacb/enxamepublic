from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class HardwareProfile:
    cpu_cores: int
    cpu_freq_mhz: float
    ram_total_gb: float
    gpu_score: float
    disk_write_mb_s: float
    disk_read_mb_s: float
    overall_score: float
    hostname: str
    platform: str

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "cpu_cores": self.cpu_cores,
            "cpu_freq_mhz": round(self.cpu_freq_mhz, 2),
            "ram_total_gb": round(self.ram_total_gb, 2),
            "gpu_score": round(self.gpu_score, 2),
            "disk_write_mb_s": round(self.disk_write_mb_s, 2),
            "disk_read_mb_s": round(self.disk_read_mb_s, 2),
            "overall_score": round(self.overall_score, 3),
            "hostname": self.hostname,
            "platform": self.platform,
        }


class HardwareBenchmark:
    """Benchmark leve para classificação relativa dos nós do cluster."""

    def __init__(self, sample_mb: int = 64) -> None:
        self.sample_mb = max(8, sample_mb)

    def run(self) -> HardwareProfile:
        cpu_cores = max(1, os.cpu_count() or 1)
        cpu_freq = self._cpu_freq_mhz()
        ram_gb = self._ram_total_gb()
        gpu_score = self._gpu_score()
        write_mb_s, read_mb_s = self._disk_speed_mb_s()
        overall = self._score(
            cpu_cores=cpu_cores,
            cpu_freq_mhz=cpu_freq,
            ram_gb=ram_gb,
            gpu_score=gpu_score,
            disk_write_mb_s=write_mb_s,
            disk_read_mb_s=read_mb_s,
        )
        return HardwareProfile(
            cpu_cores=cpu_cores,
            cpu_freq_mhz=cpu_freq,
            ram_total_gb=ram_gb,
            gpu_score=gpu_score,
            disk_write_mb_s=write_mb_s,
            disk_read_mb_s=read_mb_s,
            overall_score=overall,
            hostname=platform.node() or "unknown",
            platform=platform.platform(),
        )

    def _cpu_freq_mhz(self) -> float:
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                freqs = []
                for line in f:
                    if line.lower().startswith("cpu mhz"):
                        value = float(line.split(":", 1)[1].strip())
                        freqs.append(value)
                if freqs:
                    return sum(freqs) / len(freqs)
        except Exception:
            pass
        return 2000.0

    def _ram_total_gb(self) -> float:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = float(line.split()[1])
                        return kb / (1024 * 1024)
        except Exception:
            pass
        return 4.0

    def _gpu_score(self) -> float:
        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            return 0.0
        try:
            out = subprocess.check_output(
                [
                    nvidia_smi,
                    "--query-gpu=memory.total,clocks.max.sm",
                    "--format=csv,noheader,nounits",
                ],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            )
            score = 0.0
            for row in out.strip().splitlines():
                parts = [p.strip() for p in row.split(",")]
                if len(parts) != 2:
                    continue
                mem_mb = float(parts[0] or 0)
                clk = float(parts[1] or 0)
                score += (mem_mb / 1024.0) * max(1.0, clk / 1000.0)
            return score
        except Exception:
            return 0.0

    def _disk_speed_mb_s(self) -> tuple[float, float]:
        size = self.sample_mb * 1024 * 1024
        payload = b"0" * min(1024 * 1024, size)
        try:
            with tempfile.NamedTemporaryFile(delete=True, dir="/tmp") as tf:
                path = Path(tf.name)

                chunks = max(1, size // len(payload))
                t0 = time.perf_counter()
                for _ in range(chunks):
                    tf.write(payload)
                tf.flush()
                os.fsync(tf.fileno())
                t1 = time.perf_counter()
                write_sec = max(1e-6, t1 - t0)
                write_mb_s = (chunks * len(payload) / (1024 * 1024)) / write_sec

                t2 = time.perf_counter()
                _ = path.read_bytes()
                t3 = time.perf_counter()
                read_sec = max(1e-6, t3 - t2)
                read_mb_s = (chunks * len(payload) / (1024 * 1024)) / read_sec
                return write_mb_s, read_mb_s
        except Exception:
            return 80.0, 120.0

    def _score(
        self,
        *,
        cpu_cores: int,
        cpu_freq_mhz: float,
        ram_gb: float,
        gpu_score: float,
        disk_write_mb_s: float,
        disk_read_mb_s: float,
    ) -> float:
        cpu_component = (cpu_cores * max(cpu_freq_mhz, 800.0) / 1000.0) * 0.35
        ram_component = max(ram_gb, 1.0) * 0.25
        gpu_component = gpu_score * 0.15
        disk_component = ((disk_write_mb_s + disk_read_mb_s) / 2.0) / 100.0 * 0.25
        return cpu_component + ram_component + gpu_component + disk_component
