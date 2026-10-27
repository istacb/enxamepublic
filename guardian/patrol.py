from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .guardian import Guardian

logger = logging.getLogger('guardian.patrol')

try:
    import psutil
except ImportError:  # pragma: no cover - psutil é opcional em runtime
    psutil = None


def collect_local_metrics() -> dict[str, float]:
    """Coleta métricas locais leves para a ronda do Guardião.

    Usa psutil quando disponível; caso contrário, degrada de forma
    silenciosa (retorna 0.0) em vez de quebrar a ronda por falta de uma
    dependência opcional.
    """
    if psutil is None:
        return {'cpu': 0.0, 'mem': 0.0, 'response_time': 0.0}
    try:
        return {
            'cpu': float(psutil.cpu_percent(interval=0.3)),
            'mem': float(psutil.virtual_memory().percent),
            'response_time': 0.0,
        }
    except Exception:  # pragma: no cover - defensivo
        return {'cpu': 0.0, 'mem': 0.0, 'response_time': 0.0}


class GuardianPatrol:
    """Ronda contínua do Guardião em um node do Enxame.

    - Se `local_callback` for informado, este node É o Juiz: os alertas são
      entregues por chamada direta em processo (sem rede), e o Juiz agrega
      tudo o que recebe (tanto da própria ronda local quanto das rondas
      recebidas de outros nodes via HTTP).
    - Se `remote_reporter` for informado, este node NÃO é o Juiz: os
      alertas são enviados para o Juiz por essa função (tipicamente um
      POST assinado em /api/v1/guardian/report).

    Quando nenhuma anomalia é encontrada, nada é enviado — a ronda não gera
    tráfego/ruído em operação normal.
    """

    def __init__(
        self,
        node_id: str,
        interval_seconds: float = 15.0,
        local_callback: Callable[[dict[str, Any]], None] | None = None,
        remote_reporter: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        metrics_source: Callable[[], dict[str, float]] = collect_local_metrics,
    ) -> None:
        self.node_id = node_id
        self.interval_seconds = interval_seconds
        self.guardian = Guardian(node_id)
        self.local_callback = local_callback
        self.remote_reporter = remote_reporter
        self.metrics_source = metrics_source
        self._running = False

    async def _tick(self) -> None:
        metrics = self.metrics_source()
        alert = self.guardian.build_alert(metrics)
        if alert is None:
            return
        logger.warning('Guardião detectou anomalia em %s: %s', self.node_id, alert['anomalies'])
        await self._dispatch(alert)

    async def _dispatch(self, alert: dict[str, Any]) -> None:
        if self.local_callback is not None:
            self.local_callback(alert)
            return
        if self.remote_reporter is not None:
            try:
                await self.remote_reporter(alert)
            except Exception as exc:  # pragma: no cover - a ronda não pode derrubar o node
                logger.warning('Falha ao reportar alerta do Guardião ao Juiz: %s', exc)

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._tick()
            except Exception as exc:  # pragma: no cover - a ronda nunca deve travar o node
                logger.warning('Erro na ronda do Guardião: %s', exc)
            await asyncio.sleep(self.interval_seconds)

    def stop(self) -> None:
        self._running = False
