"""Playroom — Test prompts across multiple adapters and compare outputs."""

import json
from typing import Any

import yaml

from neuralclaw.core.bridge import load_adapter, build_context_export


def _load_adapter_yaml(adapter_name: str) -> dict[str, Any]:
    """Load raw adapter YAML for inspection."""
    from pathlib import Path
    adapter_file = Path(__file__).parent.parent / "adapters" / f"{adapter_name}.yaml"
    if not adapter_file.exists():
        raise ValueError(f"Adapter '{adapter_name}' not found at {adapter_file}")
    return yaml.safe_load(adapter_file.read_text())


def test_prompt(
    prompt: str,
    adapter_names: list[str],
    project_id: str | None = None,
) -> dict[str, Any]:
    """Test a prompt across multiple adapters and return formatted outputs.

    Returns a dict with adapter results and a comparison table.
    """
    results: dict[str, dict[str, Any]] = {}

    for adapter_name in adapter_names:
        # Load raw adapter config
        adapter_cfg = _load_adapter_yaml(adapter_name)

        # Build context export using this adapter
        try:
            export = build_context_export(
                task=prompt,
                project_id=project_id,
                adapter_name=adapter_name,
                include_vars=False,
                query=None,
            )
        except Exception as exc:
            results[adapter_name] = {
                "success": False,
                "error": str(exc),
                "config": adapter_cfg,
                "formatted": None,
            }
            continue

        # Format output based on adapter preferences
        adapter_prefs = adapter_cfg.get("preferences", {})
        fmt_pref = adapter_prefs.get("format_preference", "markdown")
        style_pref = adapter_prefs.get("style", "direct")

        formatted = _format_for_adapter(export, adapter_cfg, fmt_pref, style_pref)

        results[adapter_name] = {
            "success": True,
            "adapter": adapter_name,
            "config": adapter_cfg,
            "formatted": formatted,
            "metadata": export.get("metadata", {}),
            "constraints": export.get("constraints", []),
            "warnings": export.get("warnings", []),
            "context_items": export.get("context", []),
        }

    # Build comparison summary
    comparison = _build_comparison(results, adapter_names)

    return {
        "prompt": prompt,
        "adapters": adapter_names,
        "results": results,
        "comparison": comparison,
    }


def _format_for_adapter(
    export: dict[str, Any],
    adapter_cfg: dict[str, Any],
    fmt_pref: str,
    style_pref: str,
) -> str:
    """Format context export according to adapter preferences."""
    prepend = adapter_cfg.get("context_format", {}).get("prepend", "")
    append = adapter_cfg.get("context_format", {}).get("append", "")
    ctx_format = adapter_cfg.get("context_format", {})

    lines: list[str] = []

    if prepend:
        lines.append(prepend.strip())

    # Format each context item
    items = export.get("context", [])
    if not items:
        lines.append("(no context items)")
    else:
        if fmt_pref == "markdown":
            lines.append("### Context Items\n")
            for item in items:
                md = _item_as_markdown(item)
                lines.append(md)
        elif fmt_pref == "structured":
            lines.append("Context Items:")
            for item in items:
                lines.append(_item_as_structured(item))
        else:
            for item in items:
                lines.append(f"- {item['key']}: {item['value']}")

    if append:
        lines.append(append.strip())

    return "\n".join(lines)


def _item_as_markdown(item: dict[str, Any]) -> str:
    """Format a context item as markdown."""
    tags_str = ", ".join(f"`{t}`" for t in item.get("tags", [])) if item.get("tags") else ""
    confidence = item.get("confidence", 1.0)
    state = item.get("state", "active")

    header = f"### `{item['key']}`"
    meta = f"_{state.upper()}_ | confidence: {confidence:.0%}"
    if tags_str:
        meta += f" | {tags_str}"
    meta += "  "

    return f"{header}\n\n{meta}\n\n{item['value']}\n"


def _item_as_structured(item: dict[str, Any]) -> str:
    """Format a context item as structured plain text."""
    tags = item.get("tags", [])
    return (
        f"  KEY: {item['key']}\n"
        f"  VALUE: {item['value']}\n"
        f"  TYPE: {item['type']} | STATE: {item['state']} | CONF: {item.get('confidence', 1.0):.0%}\n"
        f"  TAGS: {', '.join(tags) if tags else '(none)'}"
    )


def _build_comparison(results: dict[str, dict[str, Any]], adapter_names: list[str]) -> dict[str, Any]:
    """Build a side-by-side comparison of adapter results."""
    comparison = {
        "adapter_count": len(adapter_names),
        "successful": sum(1 for r in results.values() if r.get("success")),
        "failed": sum(1 for r in results.values() if not r.get("success")),
        "adapter_meta": {},
    }

    for name in adapter_names:
        r = results.get(name, {})
        cfg = r.get("config", {})
        prefs = cfg.get("preferences", {})
        ctx_fmt = cfg.get("context_format", {})
        comparison["adapter_meta"][name] = {
            "max_tokens": cfg.get("max_tokens"),
            "length_pref": prefs.get("length"),
            "style_pref": prefs.get("style"),
            "format_pref": prefs.get("format_preference"),
            "supports_system": cfg.get("supports_system"),
            "supports_functions": cfg.get("supports_functions"),
            "prepend": ctx_fmt.get("prepend", "")[:50],
            "append": ctx_fmt.get("append", "")[:50],
            "context_items_count": len(r.get("context_items", [])),
            "warnings_count": len(r.get("warnings", [])),
            "constraints_count": len(r.get("constraints", [])),
        }

    return comparison


def print_comparison(comparison_result: dict[str, Any]) -> None:
    """Print a human-readable comparison table using rich."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    results = comparison_result["results"]
    comp = comparison_result["comparison"]

    table = Table(title=f"Playroom — Adapter Comparison ({comp['successful']}/{comp['adapter_count']} successful)")
    table.add_column("Adapter", style="cyan")
    table.add_column("Max Tokens", style="magenta")
    table.add_column("Length Pref", style="yellow")
    table.add_column("Style", style="green")
    table.add_column("Format", style="blue")
    table.add_column("Items", style="white")
    table.add_column("Warnings", style="red")
    table.add_column("Status", style="bold")

    for name, meta in comp["adapter_meta"].items():
        r = results.get(name, {})
        status = "✓" if r.get("success") else f"✗ {r.get('error', '')}"
        table.add_row(
            name,
            str(meta["max_tokens"] or "-"),
            meta["length_pref"] or "-",
            meta["style_pref"] or "-",
            meta["format_pref"] or "-",
            str(meta["context_items_count"]),
            str(meta["warnings_count"]),
            status,
        )

    console.print(table)

    # Print formatted output for each adapter
    console.print("\n[bold]Formatted Outputs:[/bold]\n")
    for name, r in results.items():
        if not r.get("success"):
            console.print(f"[red]✗ {name}:[/red] {r.get('error')}")
            continue
        console.print(f"[cyan]═══ {name} ═══[/cyan]")
        console.print(r.get("formatted", ""))
        console.print()
