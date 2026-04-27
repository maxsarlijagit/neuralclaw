"""Rich TUI - Interactive terminal UI for NeuralClaw."""

import sys
import time
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich import box
from typing import Optional

from neuralclaw.db.connection import db_exists, init_db
from neuralclaw.core.projects import list_projects, get_project, create_project, archive_project
from neuralclaw.core.context import search_context, add_context_item, delete_context_item, count_context_items
from neuralclaw.core.vault import vault_list, vault_exists, vault_set, vault_delete
from neuralclaw.ui.dashboard import Dashboard


console = Console()


class NeuralClawTUI:
    """Interactive TUI for NeuralClaw."""

    def __init__(self):
        self.current_project: Optional[str] = None
        self.search_query = ""
        self.mode = "main"  # main, search, vault, doctor
        self.running = True
        self.dashboard = Dashboard()

    def run(self):
        """Run the TUI main loop."""
        if not db_exists():
            console.print("[yellow]Database not initialized. Running neuralclaw init...[/yellow]")
            init_db()

        try:
            self._run_input_loop()
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            sys.exit(0)

    def _run_input_loop(self):
        """Simple input loop with live display."""
        self._render_main()
        while self.running:
            try:
                key = self._read_key()
                self._handle_key(key)
            except KeyboardInterrupt:
                self.running = False

    def _read_key(self) -> str:
        """Read a single keypress (simplified)."""
        import select
        if select.select([sys.stdin], [], [], 0.5)[0]:
            return sys.stdin.read(1)
        return ""

    def _handle_key(self, key: str):
        """Handle keyboard input."""
        if key == "\x11":  # Ctrl+Q
            self.running = False
        elif key == "\x1b":  # ESC
            # Could handle arrow keys here
            self.mode = "main"
        elif key in ("1", "F1"):
            self._show_help()
        elif key in ("2", "F2"):
            self._show_doctor()
        elif key in ("3", "F3"):
            self._show_fresh()

    def _render_main(self):
        """Render the main TUI layout."""
        console.clear()
        project_label = self.current_project or "none"
        console.print(f"[bold]NeuralClaw TUI[/bold]          [project: [cyan]{project_label}[/cyan]]")
        console.print("[dim]" + "─" * 60 + "[/dim]")

        # Left sidebar
        self._render_sidebar()

        # Main content
        self._render_main_content()

        # Footer
        console.print("")
        console.print("[dim][F1] Help  [F2] Doctor  [F3] Fresh  [Ctrl+Q] Quit[/dim]")

    def _render_sidebar(self):
        """Render the left sidebar with projects and vault."""
        projects = list_projects(status=None)
        active = [p for p in projects if p["status"] == "active"]

        console.print("")
        console.print("[bold blue]Projects[/bold blue]")
        console.print("[dim]" + "─" * 16 + "[/dim]")
        for p in active:
            marker = ">" if p["name"] == self.current_project else " "
            total = count_context_items(project_id=p["id"])
            console.print(f"{marker} [cyan]{p['name']}[/cyan] [dim]({total})[/dim]")

        console.print("")
        secrets = vault_list() if vault_exists() else []
        vault_count = len(secrets)
        console.print(f"[bold green]Vault ({vault_count})[/bold green]")
        console.print("[dim]" + "─" * 16 + "[/dim]")
        if not secrets:
            console.print("  [dim]no secrets[/dim]")
        else:
            for name in secrets[:5]:
                console.print(f"  > [cyan]{name}[/cyan]")
            if vault_count > 5:
                console.print(f"  [dim]...and {vault_count - 5} more[/dim]")

    def _render_main_content(self):
        """Render the main content area."""
        console.print("[bold]Search:[/bold] ", end="")
        console.print("[dim](type and press Enter to search)[/dim]")
        console.print("")

        results = search_context(
            query=self.search_query or None,
            project_id=self.current_project,
            limit=15,
        )

        if not results:
            console.print("[dim]No context items yet. Add some with: neuralclaw add[/dim]")
            return

        table = Table(show_header=True, box=box.ROUNDED)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("Type", style="magenta")
        table.add_column("State", style="green")

        for r in results:
            key = r["key"][:25]
            value = r["value"][:45]
            state = r["state"]
            table.add_row(key, value, r["type"], state)

        console.print(table)

    def _show_help(self):
        """Show help overlay."""
        console.print("")
        console.print(Panel(
            "[bold]NeuralClaw TUI Help[/bold]\n\n"
            "[cyan]Navigation:[/cyan]\n"
            "  F1         Show this help\n"
            "  F2         Run Doctor health check\n"
            "  F3         Show FreshApple\n"
            "  Ctrl+Q     Quit\n\n"
            "[cyan]Projects:[/cyan]\n"
            "  neuralclaw project create <name>  Create project\n"
            "  neuralclaw project list             List projects\n"
            "  neuralclaw project archive <name>  Archive\n\n"
            "[cyan]Context:[/cyan]\n"
            "  neuralclaw add 'key=value' -p <project>  Add item\n"
            "  neuralclaw search -p <project>            Search\n\n"
            "[cyan]Vault:[/cyan]\n"
            "  neuralclaw vault set <name> <value>  Store secret\n"
            "  neuralclaw vault list                 List secrets\n"
            "  neuralclaw vault get <name>           Get secret\n"
        ))
        Prompt.ask("[dim]Press Enter to continue[/dim]")

    def _show_doctor(self):
        """Run and display doctor health check."""
        console.print("")
        console.print("[bold cyan]Running Doctor health check...[/bold cyan]")
        console.print("[dim]" + "─" * 40 + "[/dim]")

        issues = []
        warnings = []

        if not db_exists():
            issues.append("Database not initialized")
        else:
            total = count_context_items()
            console.print(f"  Database: [green]✓[/green] initialized ({total} items)")

        if not vault_exists():
            warnings.append("Vault not initialized (run neuralclaw init)")
        else:
            secrets = vault_list()
            console.print(f"  Vault: [green]✓[/green] initialized ({len(secrets)} secrets)")

        if self.current_project:
            project = get_project(self.current_project)
            if project:
                stale = count_context_items(project_id=project["id"], state="stale")
                active = count_context_items(project_id=project["id"], state="active")
                console.print(f"  Project '{self.current_project}': [green]✓[/green] ({active} active, {stale} stale)")

        console.print("")
        if issues:
            for issue in issues:
                console.print(f"[red]✗ {issue}[/red]")
        if warnings:
            for warning in warnings:
                console.print(f"[yellow]⚠ {warning}[/yellow]")
        if not issues and not warnings:
            console.print("[green]✓ All systems healthy[/green]")

        Prompt.ask("[dim]Press Enter to continue[/dim]")

    def _show_fresh(self):
        """Show FreshApple panel."""
        console.print("")
        console.print("[bold green]FreshApple[/bold green]")
        console.print("[dim]" + "─" * 40 + "[/dim]")

        if not self.current_project:
            console.print("[yellow]No project selected[/yellow]")
        else:
            project = get_project(self.current_project)
            if not project:
                console.print("[yellow]Project not found[/yellow]")
            else:
                items = search_context(project_id=project["id"], state="active", limit=5)
                if not items:
                    console.print("[dim]No recent context for this project[/dim]")
                else:
                    for item in items:
                        console.print(f"  [cyan]{item['key']}[/cyan]: {item['value'][:50]}")

        Prompt.ask("[dim]Press Enter to continue[/dim]")


def run_tui():
    """Entry point for the TUI."""
    tui = NeuralClawTUI()
    tui.run()