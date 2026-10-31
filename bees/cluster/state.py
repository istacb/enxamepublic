"""Estado persistido do cluster Enxame - I/O e utilitários."""

from __future__ import annotations

from pathlib import Path

from .types import ClusterState, load_cluster_state as _load, save_cluster_state as _save


# Re-export
__all__ = ["ClusterState", "load_cluster_state", "save_cluster_state", "get_cluster_state_path"]


def get_cluster_state_path(data_dir: Path) -> Path:
    """Retorna caminho do arquivo de estado do cluster."""
    return data_dir / "cluster_state.json"


def load_cluster_state(data_dir: Path) -> ClusterState:
    """Carrega estado do cluster do disco."""
    path = get_cluster_state_path(data_dir)
    if path.exists():
        try:
            import json
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return ClusterState.from_dict(data)
        except Exception:
            pass
    return ClusterState()


def save_cluster_state(data_dir: Path, state: ClusterState) -> None:
    """Salva estado do cluster no disco."""
    path = get_cluster_state_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)