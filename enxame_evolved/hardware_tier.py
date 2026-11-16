#!/usr/bin/env python3
"""
hardware_tier.py — Coleta Universal STE-100 (U1–U6) e Classificação CPU-First
=============================================================================
Mede estado da máquina em Linux, macOS e Windows com degradação graciosa (-1),
oculta segredos (`sem_segredos`), e classifica o patamar de CPU (`legado`,
`padrao`, `performance`) para calibrar concorrência, janela de contexto e
expectativa transparente de tempo de resposta.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import psutil
except Exception:  # pragma: no cover - fallback puro stdlib (Regra U1)
    psutil = None

PADRAO_SEGREDO = re.compile(
    r"(TOKEN|CHAVE|KEY|SECRET|SENHA|PASSWORD|CREDENTIAL|AUTH)", re.IGNORECASE
)


def sem_segredos(dados: dict[str, Any]) -> dict[str, Any]:
    """Substitui valores de chaves sensíveis pelo marcador PADRAO_SEGREDO."""
    limpo: dict[str, Any] = {}
    for chave, valor in dados.items():
        if PADRAO_SEGREDO.search(str(chave)):
            limpo[chave] = "PADRAO_SEGREDO"
        elif isinstance(valor, dict):
            limpo[chave] = sem_segredos(valor)
        else:
            limpo[chave] = valor
    return limpo


def variaveis_publicas(prefixos: tuple[str, ...] = ("ENXAME_", "BEE_", "PAINEL_")) -> dict[str, Any]:
    """Retorna variáveis públicas do pacote sem expor segredos."""
    bruto = {
        k: v for k, v in os.environ.items()
        if any(k.startswith(pref) for pref in prefixos)
    }
    return sem_segredos(bruto)


def _rodar_cmd(comando: list[str], segundos: int = 5) -> str:
    """Executa comando externo verificando shutil.which (Regra U4)."""
    if not comando or not shutil.which(comando[0]):
        return ""
    try:
        proc = subprocess.run(
            comando, capture_output=True, text=True, timeout=segundos, check=False
        )
        return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def detectar_avx2() -> bool:
    """Detecta suporte a AVX2 na CPU (Linux, macOS, Windows)."""
    sistema = platform.system()
    maq = platform.machine().lower()
    if maq in ("arm64", "aarch64"):
        # NEON vetorial presente em ARM64 moderno
        return True
    if sistema == "Linux":
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.exists():
            try:
                return "avx2" in cpuinfo.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                return False
    elif sistema == "Darwin":
        saida = _rodar_cmd(["sysctl", "-a"], segundos=3)
        return "avx2" in saida.lower()
    elif sistema == "Windows":
        # Heurística não bloqueante via variáveis de família x86_64 moderna
        proc_id = os.environ.get("PROCESSOR_IDENTIFIER", "").lower()
        return "family 6" in proc_id or "amd64" in proc_id
    return False


def detectar_modelo_cpu() -> str:
    """Obtém nome legível do processador com fallback gracioso."""
    sistema = platform.system()
    if sistema == "Linux":
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.exists():
            try:
                for linha in cpuinfo.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if "model name" in linha.lower() and ":" in linha:
                        return linha.split(":", 1)[1].strip()
            except OSError:
                pass
    elif sistema == "Darwin":
        nome = _rodar_cmd(["sysctl", "-n", "machdep.cpu.brand_string"], segundos=3)
        if nome:
            return nome
    prop = platform.processor()
    return prop.strip() if prop else platform.machine() or "sem dados"


def ler_temperatura_cpu() -> float:
    """Lê temperatura em °C ou devolve -1.0 quando indisponível (Regra U6)."""
    if psutil and hasattr(psutil, "sensors_temperatures"):
        try:
            temps = psutil.sensors_temperatures() or {}
            for entradas in temps.values():
                for item in entradas:
                    atual = getattr(item, "current", None)
                    if isinstance(atual, (int, float)) and 0 < atual < 130:
                        return round(float(atual), 1)
        except Exception:
            pass
    if platform.system() == "Linux":
        base = Path("/sys/class/thermal")
        if base.exists():
            for zona in sorted(base.glob("thermal_zone*/temp")):
                try:
                    mili = int(zona.read_text(encoding="utf-8").strip())
                    if 1000 < mili < 130000:
                        return round(mili / 1000.0, 1)
                except (OSError, ValueError):
                    continue
    return -1.0


def ler_cpu_percentual() -> float:
    """Uso percentual da CPU. Devolve -1.0 na falha (Regra U6)."""
    if psutil:
        try:
            return round(float(psutil.cpu_percent(interval=0.05)), 1)
        except Exception:
            pass
    sistema = platform.system()
    if sistema == "Linux":
        stat = Path("/proc/stat")
        if stat.exists():
            try:
                antes = [int(x) for x in stat.read_text().splitlines()[0].split()[1:]]
                time.sleep(0.1)
                depois = [int(x) for x in stat.read_text().splitlines()[0].split()[1:]]
                total = sum(depois) - sum(antes)
                ocioso = (depois[3] + depois[4]) - (antes[3] + antes[4])
                return round(100.0 * (1.0 - ocioso / total), 1) if total > 0 else -1.0
            except Exception:
                return -1.0
    return -1.0


def ler_memoria_info() -> tuple[float, float, float]:
    """Devolve (percentual_usado, total_gb, livre_gb) ou (-1.0, -1.0, -1.0)."""
    if psutil:
        try:
            vm = psutil.virtual_memory()
            return (
                round(float(vm.percent), 1),
                round(vm.total / (1024**3), 1),
                round(vm.available / (1024**3), 1),
            )
        except Exception:
            pass
    if platform.system() == "Linux":
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            try:
                dados: dict[str, int] = {}
                for linha in meminfo.read_text().splitlines():
                    chave, _, resto = linha.partition(":")
                    if resto.strip():
                        dados[chave.strip()] = int(resto.split()[0])
                total_kb = dados.get("MemTotal", 0)
                disp_kb = dados.get("MemAvailable", dados.get("MemFree", 0))
                if total_kb > 0:
                    pct = round(100.0 * (1.0 - disp_kb / total_kb), 1)
                    return pct, round(total_kb / 1048576.0, 1), round(disp_kb / 1048576.0, 1)
            except Exception:
                pass
    return -1.0, -1.0, -1.0


def ler_disco_info(caminho: str | Path | None = None) -> dict[str, Any]:
    """Devolve informações de disco com degradação graciosa (-1.0)."""
    alvo = str(caminho or Path.home())
    try:
        uso = shutil.disk_usage(alvo)
        return {
            "caminho": alvo,
            "total_gb": round(uso.total / (1024**3), 1),
            "livre_gb": round(uso.free / (1024**3), 1),
            "percentual": round(100.0 * uso.used / uso.total, 1) if uso.total else -1.0,
        }
    except OSError:
        return {"caminho": alvo, "total_gb": -1.0, "livre_gb": -1.0, "percentual": -1.0}


@dataclass(slots=True)
class CpuHardwareProfile:
    """Perfil completo de hardware CPU da máquina e expectativa de tempo."""

    machine_alias: str
    os_name: str
    os_version: str
    architecture: str
    cpu_model: str
    cpu_cores_physical: int
    cpu_cores_logical: int
    cpu_freq_ghz: float
    avx2_supported: bool
    ram_total_gb: float
    ram_free_gb: float
    ram_pct: float
    cpu_pct: float
    temp_celsius: float
    disk: dict[str, Any]
    ssh_available: bool
    tier: str  # "legado" | "padrao" | "performance"
    tier_label: str
    est_tokens_per_sec: float
    est_image_seconds: int
    recommended_num_ctx: int
    recommended_threads: int
    pacing_notice: str
    collected_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    # --- Aliases de compatibilidade (EnxameKernel / Orquestrador) ---
    @property
    def os_release(self) -> str:
        return self.os_version

    @property
    def cores_physical(self) -> int:
        return self.cpu_cores_physical

    @property
    def cores_logical(self) -> int:
        return self.cpu_cores_logical

    @property
    def has_avx2(self) -> bool:
        return self.avx2_supported

    @property
    def has_avx(self) -> bool:
        return self.avx2_supported

    @property
    def disk_free_gb(self) -> float:
        try:
            return float((self.disk or {}).get("livre_gb", -1.0))
        except (TypeError, ValueError):
            return -1.0

    @property
    def disk_total_gb(self) -> float:
        try:
            return float((self.disk or {}).get("total_gb", -1.0))
        except (TypeError, ValueError):
            return -1.0

    @property
    def disk_pct(self) -> float:
        try:
            return float((self.disk or {}).get("percentual", -1.0))
        except (TypeError, ValueError):
            return -1.0


def classificar_hardware_cpu(
    cores_physical: int,
    cores_logical: int,
    ram_total_gb: float,
    avx2: bool,
) -> dict[str, Any]:
    """
    Classifica máquina puramente em CPU para calibrar latência esperada,
    threads do Ollama e janela de contexto sem travar máquinas antigas.
    """
    eff_cores = max(1, cores_physical if cores_physical > 0 else max(1, cores_logical // 2))
    eff_ram = ram_total_gb if ram_total_gb > 0 else 4.0
    fator_simd = 1.0 if avx2 else 0.58

    if eff_cores < 4 or eff_ram < 6.0 or not avx2:
        tier = "legado"
        tier_label = "CPU Legado"
        est_tps = round(max(1.8, eff_cores * 1.5 * fator_simd), 1)
        est_img_s = max(90, int(220 / max(1, eff_cores // 2)))
        num_ctx = 2048
        threads = max(1, min(eff_cores, 4))
        pacing = (
            f"Hardware legado ({eff_cores} núcleo(s), {eff_ram:.1f} GB RAM"
            f"{'' if avx2 else ', sem AVX2'}): processamento 100% local em CPU, "
            f"ritmo estimado ~{est_tps} tok/s. Respostas mais longas são normais."
        )
    elif eff_cores < 8 or eff_ram < 15.5:
        tier = "padrao"
        tier_label = "CPU Padrão"
        est_tps = round(max(6.0, eff_cores * 2.1 * fator_simd), 1)
        est_img_s = max(40, int(180 / eff_cores))
        num_ctx = 4096
        threads = max(2, eff_cores)
        pacing = (
            f"CPU padrão ({eff_cores} núcleos, {eff_ram:.1f} GB RAM): "
            f"inferência local estável (~{est_tps} tok/s)."
        )
    else:
        tier = "performance"
        tier_label = "CPU Multicore"
        est_tps = round(min(38.0, eff_cores * 2.4 * fator_simd), 1)
        est_img_s = max(20, int(200 / eff_cores))
        num_ctx = 6144
        threads = max(4, min(eff_cores, 16))
        pacing = (
            f"CPU multicore ({eff_cores} núcleos, {eff_ram:.1f} GB RAM, AVX2): "
            f"alta velocidade local (~{est_tps} tok/s)."
        )

    return {
        "tier": tier,
        "tier_label": tier_label,
        "est_tokens_per_sec": est_tps,
        "est_image_seconds": est_img_s,
        "recommended_num_ctx": num_ctx,
        "recommended_threads": threads,
        "pacing_notice": pacing,
    }


def coletar_perfil_cpu(
    machine_alias: str | None = None,
    disk_path: str | Path | None = None,
) -> CpuHardwareProfile:
    """Coleta instantânea e resiliente do estado e inventário da máquina."""
    apelido = (
        machine_alias
        or os.environ.get("ENXAME_APELIDO")
        or os.environ.get("PAINEL_APELIDO")
        or platform.node()
        or "enxame-local"
    )
    sistema = platform.system() or "Linux"
    versao_so = platform.release() or platform.version() or "sem dados"
    arquitetura = platform.machine() or "sem dados"

    cores_logical = os.cpu_count() or 1
    cores_physical = max(1, cores_logical // 2)
    freq_ghz = -1.0

    if psutil:
        try:
            cp = psutil.cpu_count(logical=False)
            cl = psutil.cpu_count(logical=True)
            if cp:
                cores_physical = int(cp)
            if cl:
                cores_logical = int(cl)
            fn = getattr(psutil, "cpu_freq", None)
            cf = fn() if callable(fn) else None
            if cf and getattr(cf, "current", 0):
                freq_ghz = round(float(cf.current) / 1000.0, 2)
        except Exception:
            pass

    avx2 = detectar_avx2()
    cpu_pct = ler_cpu_percentual()
    ram_pct, ram_total, ram_free = ler_memoria_info()
    disco = ler_disco_info(disk_path)
    temp_c = ler_temperatura_cpu()
    cpu_model = detectar_modelo_cpu()

    tier_info = classificar_hardware_cpu(
        cores_physical=cores_physical,
        cores_logical=cores_logical,
        ram_total_gb=ram_total,
        avx2=avx2,
    )

    return CpuHardwareProfile(
        machine_alias=apelido,
        os_name=sistema,
        os_version=versao_so,
        architecture=arquitetura,
        cpu_model=cpu_model,
        cpu_cores_physical=cores_physical,
        cpu_cores_logical=cores_logical,
        cpu_freq_ghz=freq_ghz,
        avx2_supported=avx2,
        ram_total_gb=ram_total,
        ram_free_gb=ram_free,
        ram_pct=ram_pct,
        cpu_pct=cpu_pct,
        temp_celsius=temp_c,
        disk=disco,
        ssh_available=bool(shutil.which("ssh")),
        tier=tier_info["tier"],
        tier_label=tier_info["tier_label"],
        est_tokens_per_sec=tier_info["est_tokens_per_sec"],
        est_image_seconds=tier_info["est_image_seconds"],
        recommended_num_ctx=tier_info["recommended_num_ctx"],
        recommended_threads=tier_info["recommended_threads"],
        pacing_notice=tier_info["pacing_notice"],
    )


def identidade_ste(papel: str, machine_alias: str | None = None, sistema_nome: str = "enxame") -> dict[str, Any]:
    """Contrato /ping do Manual STE-100 identificando sistema, máquina e papel."""
    apelido = (
        machine_alias
        or os.environ.get("ENXAME_APELIDO")
        or os.environ.get("PAINEL_APELIDO")
        or platform.node()
        or "enxame-local"
    )
    return {
        "ok": True,
        "sistema": sistema_nome,
        "maquina": apelido,
        "papel": papel,
        "plataforma": platform.system(),
        "python": platform.python_version(),
    }


def _ler_uptime_segundos() -> int:
    """Tempo ligado em segundos ou -1 quando indisponível (Regra U6)."""
    if psutil and hasattr(psutil, "boot_time"):
        try:
            return max(0, int(time.time() - float(psutil.boot_time())))
        except Exception:
            pass
    if platform.system() == "Linux":
        try:
            return int(float(Path("/proc/uptime").read_text().split()[0]))
        except Exception:
            pass
    return -1


def coletar_estado_ste(machine_alias: str | None = None) -> dict[str, Any]:
    """
    Contrato STE-100 `GET /estado`: estado instantâneo da máquina local com
    degradação graciosa (-1) em qualquer métrica indisponível.
    """
    inicio = time.time()
    apelido = (
        machine_alias
        or os.environ.get("ENXAME_APELIDO")
        or os.environ.get("PAINEL_APELIDO")
        or platform.node()
        or "enxame-local"
    )
    ram_pct, ram_total, ram_livre = ler_memoria_info()
    disco = ler_disco_info(None)
    cores_logical = os.cpu_count() or 1
    cores_physical = max(1, cores_logical // 2)
    if psutil:
        try:
            cp = psutil.cpu_count(logical=False)
            cl = psutil.cpu_count(logical=True)
            if cp:
                cores_physical = int(cp)
            if cl:
                cores_logical = int(cl)
        except Exception:
            pass
    return {
        "ok": True,
        "maquina": apelido,
        "cpu_pct": ler_cpu_percentual(),
        "ram_pct": ram_pct,
        "ram_total_gb": ram_total,
        "ram_livre_gb": ram_livre,
        "disco_pct": disco.get("percentual", -1.0),
        "disco_total_gb": disco.get("total_gb", -1.0),
        "disco_livre_gb": disco.get("livre_gb", -1.0),
        "nucleos_fisicos": cores_physical,
        "nucleos_logicos": cores_logical,
        "temperatura_c": ler_temperatura_cpu(),
        "uptime_s": _ler_uptime_segundos(),
        "identidade": {
            "sistema": platform.system() or "Linux",
            "versao_so": platform.release() or platform.version() or "sem dados",
            "arquitetura": platform.machine() or "sem dados",
        },
        "segundos": round(time.time() - inicio, 2),
    }


def coletar_saude_ste(
    extra_checks: dict[str, Any] | None = None,
    machine_alias: str | None = None,
) -> dict[str, Any]:
    """
    Contrato STE-100 `GET /saude`: avaliação booleana + lista de avisos.
    Nunca levanta exceção; métricas indisponíveis viram avisos, não falhas.
    """
    inicio = time.time()
    estado = coletar_estado_ste(machine_alias=machine_alias)
    avisos: list[str] = []
    checks: dict[str, Any] = {}

    cpu = estado.get("cpu_pct", -1.0)
    ram = estado.get("ram_pct", -1.0)
    disco_pct = estado.get("disco_pct", -1.0)
    temp = estado.get("temperatura_c", -1.0)

    checks["cpu_ok"] = cpu < 0 or cpu < 95.0
    if cpu >= 95.0:
        avisos.append(f"CPU em nível crítico ({cpu}%)")
    checks["memoria_ok"] = ram < 0 or ram < 96.0
    if ram >= 96.0:
        avisos.append(f"Memória quase esgotada ({ram}%)")
    checks["disco_ok"] = disco_pct < 0 or disco_pct < 97.0
    if disco_pct >= 97.0:
        avisos.append(f"Disco quase cheio ({disco_pct}%)")
    checks["temperatura_ok"] = temp < 0 or temp < 92.0
    if temp >= 92.0:
        avisos.append(f"Temperatura alta da CPU ({temp} °C)")

    for nome, valor in (extra_checks or {}).items():
        checks[str(nome)] = bool(valor)
        if not valor:
            avisos.append(f"Verificação '{nome}' indisponível")

    ok = all(bool(v) for v in checks.values())
    return {
        "ok": ok,
        "maquina": estado.get("maquina"),
        "avisos": avisos,
        "checks": checks,
        "cpu_pct": cpu,
        "ram_pct": ram,
        "disco_pct": disco_pct,
        "temperatura_c": temp,
        "uptime_s": estado.get("uptime_s", -1),
        "segundos": round(time.time() - inicio, 2),
    }


def detect_cpu_hardware_profile(
    machine_alias: str | None = None,
    disk_path: str | Path | None = None,
) -> CpuHardwareProfile:
    """Alias em inglês de `coletar_perfil_cpu` usado pelo EnxameKernel."""
    return coletar_perfil_cpu(machine_alias=machine_alias, disk_path=disk_path)


def consultar_executor_ste(
    alvo: str = "",
    caminho: str = "/estado",
    porta_exec: int = 8765,
    token: str = "",
    timeout_s: int = 8,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Consulta uma máquina remota da lista ENXAME_MAQUINAS/PAINEL_MAQUINAS.
    Tenta HTTP direto na LAN primeiro; se for apelido SSH sem porta acessível,
    usa túnel/execução SSH sem expor o token em linha de comando visível.

    Compatibilidade EnxameKernel: aceita `endpoint_or_host=`, `mode=` ("http" ou
    "ssh"), `ssh_user=` e `token=` como kwargs; nesse modo sonda `/estado` +
    `/saude` e devolve `{"ok", "estado", "saude", "erro"}`.
    """
    endpoint_or_host = str(kwargs.get("endpoint_or_host") or alvo or "").strip()
    mode = str(kwargs.get("mode") or "http").strip().lower()
    ssh_user = str(kwargs.get("ssh_user") or "").strip()
    token_kw = kwargs.get("token")
    if token_kw:
        token = str(token_kw)

    # Modo sonda combinada do EnxameKernel (inventário de máquinas remotas)
    if "endpoint_or_host" in kwargs or "mode" in kwargs or "ssh_user" in kwargs:
        if mode == "ssh":
            alvo_ssh = f"{ssh_user}@{endpoint_or_host}" if ssh_user and "@" not in endpoint_or_host else endpoint_or_host
            estado = _consultar_caminho_ste(alvo_ssh, "/estado", porta_exec, token, timeout_s)
            saude = _consultar_caminho_ste(alvo_ssh, "/saude", porta_exec, token, timeout_s)
        else:
            base = endpoint_or_host.rstrip("/")
            if base.startswith("http"):
                estado = _consultar_url_ste(f"{base}/estado", token, timeout_s)
                saude = _consultar_url_ste(f"{base}/saude", token, timeout_s)
            else:
                estado = _consultar_caminho_ste(endpoint_or_host, "/estado", porta_exec, token, timeout_s)
                saude = _consultar_caminho_ste(endpoint_or_host, "/saude", porta_exec, token, timeout_s)
        ok = bool(estado.get("ok") or saude.get("ok"))
        return {
            "ok": ok,
            "estado": estado,
            "saude": saude,
            "erro": "" if ok else str(estado.get("causa provável") or saude.get("causa provável") or "executor inacessível")[:180],
            "transporte": estado.get("transporte", "http") if estado.get("ok") else "inacessível",
            "modo": mode,
        }

    return _consultar_caminho_ste(alvo, caminho, porta_exec, token, timeout_s)


def _consultar_url_ste(url: str, token: str, timeout_s: int) -> dict[str, Any]:
    """Consulta GET JSON direta em uma URL STE-100 completa."""
    inicio = time.time()
    try:
        req = urllib.request.Request(url)
        if token:
            req.add_header("X-Painel-Token", token)
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        dados["segundos"] = round(time.time() - inicio, 2)
        return dados
    except Exception as erro:
        return {
            "ok": False,
            "cpu": -1.0,
            "memoria": -1.0,
            "causa provável": str(erro)[:180],
            "segundos": round(time.time() - inicio, 2),
        }


def _consultar_caminho_ste(
    alvo: str,
    caminho: str = "/estado",
    porta_exec: int = 8765,
    token: str = "",
    timeout_s: int = 8,
) -> dict[str, Any]:
    """Consulta um caminho STE-100 (`/estado`, `/saude`...) em host LAN ou alias SSH."""
    inicio = time.time()
    host = alvo.strip()
    porta = porta_exec
    if ":" in host and not host.startswith("["):
        h_part, _, p_part = host.partition(":")
        if p_part.isdigit():
            host = h_part
            porta = int(p_part)

    # 1. Tentativa direta HTTP LAN
    try:
        url = f"http://{host}:{porta}{caminho}"
        req = urllib.request.Request(url)
        if token:
            req.add_header("X-Painel-Token", token)
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        dados["maquina"] = dados.get("maquina", host)
        dados["segundos"] = round(time.time() - inicio, 2)
        return dados
    except Exception as erro_http:
        # 2. Fallback SSH para máquinas acessíveis apenas por túnel/alias SSH
        if shutil.which("ssh") and shutil.which("curl"):
            try:
                # Passa cabeçalho via stdin (`curl -K -`) para NÃO expor token no ps aux
                curl_cfg = f'url = "http://127.0.0.1:{porta}{caminho}"\nmax-time = 5\nsilent\n'
                if token:
                    curl_cfg += f'header = "X-Painel-Token: {token}"\n'
                cmd = [
                    "ssh",
                    "-o", "BatchMode=yes",
                    "-o", "ConnectTimeout=4",
                    host,
                    "curl -K -",
                ]
                proc = subprocess.run(
                    cmd, input=curl_cfg, capture_output=True, text=True, timeout=timeout_s, check=False
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    dados = json.loads(proc.stdout)
                    dados["maquina"] = dados.get("maquina", host)
                    dados["segundos"] = round(time.time() - inicio, 2)
                    dados["transporte"] = "ssh"
                    return dados
            except Exception:
                pass
        return {
            "ok": False,
            "maquina": host,
            "cpu": -1.0,
            "memoria": -1.0,
            "disco": {"percentual": -1.0},
            "causa provável": str(erro_http)[:180],
            "segundos": round(time.time() - inicio, 2),
        }
