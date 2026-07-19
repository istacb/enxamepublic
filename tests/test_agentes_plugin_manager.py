from __future__ import annotations

from agentes.plugin_manager import PluginManager


def test_plugin_manager_loads_default_plugins() -> None:
    manager = PluginManager()
    loaded = manager.load_all()
    names = [meta.name for meta in loaded]
    assert "programador" in names
    assert "medico" in names
    assert "matematico" in names


def test_plugin_selection_by_keyword() -> None:
    manager = PluginManager()
    manager.load_all()
    plugin = manager.best_for("Preciso traduzir este texto do inglês para português")
    assert plugin.name == "tradutor"
