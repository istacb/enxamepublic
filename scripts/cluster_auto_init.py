from __future__ import annotations

import json
import os
import time

import httpx

from core.cluster import HardwareBenchmark
from core.exp.http import build_auth_headers
from core.exp.security import EXPSecurity


def main() -> int:
    node_role = os.getenv("NODE_ROLE", "agentes")
    juiz_url = os.getenv("ENXAME_JUIZ_URL", "http://127.0.0.1:7700")
    secret = os.getenv("EXP_SHARED_SECRET", "enxame-dev-secret")

    profile = HardwareBenchmark().run()
    print("[cluster-auto-init] benchmark:")
    print(json.dumps(profile.as_dict(), ensure_ascii=False, indent=2))

    # Eleição centralizada é disparada no Juiz após os nós enviarem HELLO/heartbeat.
    if node_role != "juiz":
        print("[cluster-auto-init] nó não é Juiz; apenas benchmark local concluído.")
        return 0

    security = EXPSecurity(secret)
    body = json.dumps({"reason": "auto_init", "timestamp": int(time.time())}).encode("utf-8")
    headers = build_auth_headers(security=security, body=body)
    headers["content-type"] = "application/json"

    with httpx.Client(timeout=20) as client:
        for attempt in range(1, 6):
            try:
                resp = client.post(f"{juiz_url}/api/v1/election", content=body, headers=headers)
                if resp.status_code == 200:
                    print("[cluster-auto-init] eleição executada com sucesso:")
                    print(resp.text)
                    return 0
                print(f"[cluster-auto-init] tentativa {attempt}: HTTP {resp.status_code} - {resp.text}")
            except Exception as exc:
                print(f"[cluster-auto-init] tentativa {attempt} falhou: {exc}")
            time.sleep(3)

    print("[cluster-auto-init] não foi possível disparar eleição automática.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
