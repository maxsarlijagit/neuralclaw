"""Dashboard components for the TUI."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional

from neuralclaw.core.projects import list_projects, get_project
from neuralclaw.core.context import search_context, count_context_items
from neuralclaw.core.vault import vault_list, vault_exists
from neuralclaw.db.connection import db_exists


console = Console()


class Dashboard:
    """Dashboard displaying NeuralClaw status at a glance."""

    def __init__(self, project_name: Optional[str] = None):
        self.project_name = project_name
        self.project_id = None
        if project_name:
            project = get_project(project_name)
            if project:
                self.project_id = project["id"]

    def render_projects_panel(self) -> Panel:
        """Render the projects list panel."""
        projects = list_projects(status=None)
        active = [p for p in projects if p["status"] == "active"]
        archived = [p for p in projects if p["status"] == "archived"]

        lines = []
        for p in active:
            marker = ">" if p["name"] == self.project_name else " "
            total = count_context_items(project_id=p["id"])
            lines.append(f"{marker} [cyan]{p['name']}[/cyan] [dim]({total})[/dim]")

        if archived:
            lines.append("")
            lines.append("[dim]── archived ──[/dim]")
            for p in archived:
                lines.append(f"  [dim]{p['name']}[/dim]")

        if not lines:
            lines = ["[dim]No projects[/dim]"]

        content = "\n".join(lines)
        return Panel(content, title="Projects", border_style="blue", padding=0)

    def render_vault_panel(self) -> Panel:
        """Render the vault panel."""
        if not vault_exists():
            return Panel("[yellow]Vault not initialized[/yellow]", title="Vault", border_style="yellow")

        secrets = vault_list()
        if not secrets:
            return Panel("[dim]No secrets stored[/dim]", title="Vault (0)", border_style="green")

        lines = []
        for name in secrets:
            lines.append(f"> [cyan]{name}[/cyan]")

        content = "\n".join(lines)
        title = f"Vault ({len(secrets)})"
        return Panel(content, title=title, border_style="green", padding=0)

    def render_context_items(self, query: str = "") -> Table:
        """Render context items table."""
        results = search_context(
            query=query or None,
            project_id=self.project_id,
            limit=20,
        )

        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Key", style="cyan", no_wrap=False)
        table.add_column("Value", style="white", no_wrap=False)
        table.add_column("Type", style="magenta")
        table.add_column("State", style="green")

        if not results:
            return table

        for r in results:
            key = r["key"][:20] + "..." if len(r["key"]) > 20 else r["key"]
            value = r["value"][:40] + "..." if len(r["value"]) > 40 else r["value"]

            state_color = self._state_color(r["state"])
            state_str = f"[{state_color}]{r['state']}[/{state_color}]"

            type_icon = self._type_icon(r["type"])
            table.add_row(f"{type_icon} {key}", value, r["type"], state_str)

        return table

    def render_doctor_summary(self) -> Panel:
        """Render a quick doctor health summary."""
        issues = []
        warnings = []

        if not db_exists():
            issues.append("Database not initialized")
        else:
            total = count_context_items()
            if total == 0:
                warnings.append("No context items yet")

        if not vault_exists():
            warnings.append("Vault not initialized")

        if self.project_id:
            stale_count = count_context_items(project_id=self.project_id, state="stale")
            if stale_count > 0:
                warnings.append(f"{stale_count} stale items in project")

        lines = []
        if issues:
            for issue in issues:
                lines.append(f"[red]✗ {issue}[/red]")
        if warnings:
            for warning in warnings:
                lines.append(f"[yellow]⚠ {warning}[/yellow]")
        if not lines:
            lines = ["[green]✓ All systems healthy[/green]"]

        content = "\n".join(lines)
        return Panel(content, title="Doctor", border_style="cyan", padding=0)

    def render_freshapple(self) -> Panel:
        """Render FreshApple status panel."""
        if not self.project_id:
            return Panel("[dim]No project selected[/dim]", title="FreshApple", border_style="dim")

        items = search_context(project_id=self.project_id, state="active", limit=5)
        if not items:
            return Panel("[dim]No recent context[/dim]", title="FreshApple", border_style="dim")

        lines = []
        for item in items:
            key = item["key"][:25]
            lines.append(f"[cyan]{key}[/cyan] [dim]:[/dim] {item['value'][:40]}")

        content = "\n".join(lines)
        return Panel(content, title="FreshApple", border_style="green", padding=0)

    @staticmethod
    def _state_color(state: str) -> str:
        colors = {
            "active": "green",
            "stale": "yellow",
            "verified": "cyan",
            "deprecated": "red",
            "archived": "dim",
            "conflicting": "red",
        }
        return colors.get(state, "white")

    @staticmethod
    def _type_icon(item_type: str) -> str:
        icons = {
            "note": "📝",
            "decision": "🎯",
            "error": "❌",
            "variable": "🔗",
            "preference": "⚙️",
            "process": "⚡",
            "industry": "🏭",
        }
        return icons.get(item_type, "•")