"""NeuralClaw Plugin System.

Plugins can hook into context_search, context_export, and doctor_check.
"""

import importlib
import importlib.metadata
import logging
from pathlib import Path
from typing import Any, TypedDict

import appdirs
import yaml

logger = logging.getLogger(__name__)

# Plugin hook types
HookResults = list[dict[str, Any]]
HookExportData = dict[str, Any]
HookDoctorCheck = list[dict[str, str]]  # list of {check: str, status: str, message: str}

PLUGIN_CONFIG_DIR = Path(appdirs.user_config_dir("neuralclaw"))
PLUGIN_CONFIG_FILE = PLUGIN_CONFIG_DIR / "plugins.yaml"


class PluginHooks(TypedDict, total=False):
    """Hooks exposed by a plugin module."""

    on_context_search: Any  # (query, project_id, results) -> modified results
    on_context_export: Any  # (export_data) -> modified export_data
    on_doctor_check: Any  # () -> list of check dicts


class PluginSpec:
    """A loaded plugin."""

    name: str
    module_name: str
    hooks: PluginHooks
    enabled: bool = True

    def __init__(self, name: str, module_name: str, hooks: PluginHooks, enabled: bool = True):
        self.name = name
        self.module_name = module_name
        self.hooks = hooks
        self.enabled = enabled


# Global plugin registry
_registered_plugins: dict[str, PluginSpec] = {}


def _load_plugin_from_entrypoint(name: str, ep: importlib.metadata.EntryPoint) -> PluginSpec | None:
    """Load a plugin from an entry point."""
    try:
        mod = importlib.import_module(ep.module)
        hooks: PluginHooks = {}
        if hasattr(mod, "hooks"):
            hooks = mod.hooks()  # call hooks() to get the dict
        return PluginSpec(name=name, module_name=ep.module, hooks=hooks, enabled=True)
    except Exception as exc:
        logger.warning("Failed to load plugin '%s': %s", name, exc)
        return None


def _discover_plugins() -> dict[str, PluginSpec]:
    """Discover all installed plugins via entry points."""
    plugins: dict[str, PluginSpec] = {}

    # Load from entry points
    try:
        eps = importlib.metadata.entry_points(group="neuralclaw.plugins")
        for ep in eps:
            spec = _load_plugin_from_entrypoint(ep.name, ep)
            if spec:
                plugins[ep.name] = spec
    except Exception as exc:
        logger.warning("Could not load entry-point plugins: %s", exc)

    # Load builtins from neuralclaw.plugins.builtins
    builtins_dir = Path(__file__).parent / "builtins"
    if builtins_dir.exists():
        for py_file in builtins_dir.glob("*.py"):
            if py_file.stem.startswith("_"):
                continue
            try:
                mod = importlib.import_module(f"neuralclaw.plugins.builtins.{py_file.stem}")
                if hasattr(mod, "hooks"):
                    plugins[py_file.stem] = PluginSpec(
                        name=py_file.stem,
                        module_name=f"neuralclaw.plugins.builtins.{py_file.stem}",
                        hooks=mod.hooks(),
                        enabled=True,
                    )
            except Exception as exc:
                logger.warning("Failed to load builtin plugin '%s': %s", py_file.stem, exc)

    return plugins


def load_plugins() -> dict[str, PluginSpec]:
    """Load all plugins, respecting enabled/disabled state from config."""
    plugins = _discover_plugins()

    # Load saved enabled/disabled state
    enabled_state = _load_plugin_state()

    for name, spec in plugins.items():
        spec.enabled = enabled_state.get(name, True)

    _registered_plugins.clear()
    _registered_plugins.update(plugins)
    return plugins


def _load_plugin_state() -> dict[str, bool]:
    """Load plugin enable/disable state from config file."""
    if not PLUGIN_CONFIG_FILE.exists():
        return {}
    try:
        data = yaml.safe_load(PLUGIN_CONFIG_FILE.read_text()) or {}
        return data.get("enabled", {})
    except Exception:
        return {}


def _save_plugin_state(state: dict[str, bool]) -> None:
    """Save plugin enable/disable state to config file."""
    PLUGIN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PLUGIN_CONFIG_FILE.write_text(yaml.safe_dump({"enabled": state}, default_flow_style=False))


def list_plugins() -> list[PluginSpec]:
    """Return all loaded plugins."""
    return list(_registered_plugins.values())


def get_plugin(name: str) -> PluginSpec | None:
    """Get a plugin by name."""
    return _registered_plugins.get(name)


def enable_plugin(name: str) -> bool:
    """Enable a plugin by name. Returns True if successful."""
    spec = _registered_plugins.get(name)
    if not spec:
        return False
    spec.enabled = True
    state = _load_plugin_state()
    state[name] = True
    _save_plugin_state(state)
    return True


def disable_plugin(name: str) -> bool:
    """Disable a plugin by name. Returns True if successful."""
    spec = _registered_plugins.get(name)
    if not spec:
        return False
    spec.enabled = False
    state = _load_plugin_state()
    state[name] = False
    _save_plugin_state(state)
    return True


# ─── Hook runners ────────────────────────────────────────────────────────────

def run_context_search_hooks(
    query: str | None,
    project_id: str | None,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run on_context_search hooks on search results."""
    if not _registered_plugins:
        load_plugins()
    for spec in _registered_plugins.values():
        if not spec.enabled:
            continue
        hook = spec.hooks.get("on_context_search")
        if hook:
            try:
                results = hook(query=query, project_id=project_id, results=results)
            except Exception as exc:
                logger.warning("Plugin '%s' on_context_search failed: %s", spec.name, exc)
    return results


def run_context_export_hooks(export_data: dict[str, Any]) -> dict[str, Any]:
    """Run on_context_export hooks on export data."""
    if not _registered_plugins:
        load_plugins()
    for spec in _registered_plugins.values():
        if not spec.enabled:
            continue
        hook = spec.hooks.get("on_context_export")
        if hook:
            try:
                export_data = hook(export_data=export_data)
            except Exception as exc:
                logger.warning("Plugin '%s' on_context_export failed: %s", spec.name, exc)
    return export_data


def run_doctor_check_hooks() -> HookDoctorCheck:
    """Run on_doctor_check hooks. Returns accumulated check results."""
    if not _registered_plugins:
        load_plugins()
    all_checks: HookDoctorCheck = []
    for spec in _registered_plugins.values():
        if not spec.enabled:
            continue
        hook = spec.hooks.get("on_doctor_check")
        if hook:
            try:
                checks = hook() or []
                all_checks.extend(checks)
            except Exception as exc:
                logger.warning("Plugin '%s' on_doctor_check failed: %s", spec.name, exc)
    return all_checks
