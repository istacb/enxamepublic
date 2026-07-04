from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from agentes.plugins.base import SpecialtyPlugin


@dataclass(slots=True)
class PluginMeta:
    name: str
    module: str
    version: str
    description: str
    mtime: float


class PluginManager:
    """Gerencia plugins de especialidades com hot-load/hot-unload."""

    def __init__(self, package: str = "agentes.plugins") -> None:
        self.package = package
        self._plugins: dict[str, SpecialtyPlugin] = {}
        self._modules: dict[str, ModuleType] = {}
        self._meta: dict[str, PluginMeta] = {}

    def load_all(self) -> list[PluginMeta]:
        pkg = importlib.import_module(self.package)
        loaded: list[PluginMeta] = []
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name.startswith("_") or info.name == "base":
                continue
            meta = self.load_plugin(info.name)
            if meta:
                loaded.append(meta)
        return loaded

    def list_plugins(self) -> list[PluginMeta]:
        return sorted(self._meta.values(), key=lambda m: m.name)

    def get(self, name: str) -> SpecialtyPlugin | None:
        return self._plugins.get(name)

    def best_for(self, text: str, fallback: str = "programador") -> SpecialtyPlugin:
        ranked = [(plugin.match_score(text), plugin) for plugin in self._plugins.values()]
        ranked.sort(key=lambda item: item[0], reverse=True)
        if ranked and ranked[0][0] > 0:
            return ranked[0][1]
        if fallback in self._plugins:
            return self._plugins[fallback]
        if self._plugins:
            return next(iter(self._plugins.values()))
        raise RuntimeError("Nenhum plugin carregado")

    def load_plugin(self, module_name: str) -> PluginMeta | None:
        full_module = f"{self.package}.{module_name}"
        module = importlib.import_module(full_module)
        plugin = self._build_plugin(module)
        if plugin is None:
            return None

        file_path = Path(getattr(module, "__file__", ""))
        mtime = file_path.stat().st_mtime if file_path.exists() else 0.0
        self._plugins[plugin.name] = plugin
        self._modules[plugin.name] = module
        meta = PluginMeta(
            name=plugin.name,
            module=full_module,
            version=plugin.version,
            description=plugin.description,
            mtime=mtime,
        )
        self._meta[plugin.name] = meta
        return meta

    def unload_plugin(self, plugin_name: str) -> bool:
        exists = plugin_name in self._plugins
        self._plugins.pop(plugin_name, None)
        self._meta.pop(plugin_name, None)
        self._modules.pop(plugin_name, None)
        return exists

    def reload_plugin(self, plugin_name: str) -> PluginMeta | None:
        module = self._modules.get(plugin_name)
        if module is None:
            return self.load_plugin(plugin_name)
        module = importlib.reload(module)
        plugin = self._build_plugin(module)
        if plugin is None:
            return None
        file_path = Path(getattr(module, "__file__", ""))
        mtime = file_path.stat().st_mtime if file_path.exists() else 0.0
        self._plugins[plugin.name] = plugin
        self._modules[plugin.name] = module
        meta = PluginMeta(
            name=plugin.name,
            module=module.__name__,
            version=plugin.version,
            description=plugin.description,
            mtime=mtime,
        )
        self._meta[plugin.name] = meta
        return meta

    def refresh_changed(self) -> list[PluginMeta]:
        changed: list[PluginMeta] = []
        for meta in list(self._meta.values()):
            module = self._modules.get(meta.name)
            if not module:
                continue
            path = Path(getattr(module, "__file__", ""))
            if not path.exists():
                continue
            mtime = path.stat().st_mtime
            if mtime > meta.mtime:
                reloaded = self.reload_plugin(meta.name)
                if reloaded:
                    changed.append(reloaded)
        return changed

    def _build_plugin(self, module: ModuleType) -> SpecialtyPlugin | None:
        plugin_cls = getattr(module, "PLUGIN_CLASS", None)
        if plugin_cls and inspect.isclass(plugin_cls) and issubclass(plugin_cls, SpecialtyPlugin):
            return plugin_cls()

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, SpecialtyPlugin) and obj is not SpecialtyPlugin:
                return obj()
        return None
