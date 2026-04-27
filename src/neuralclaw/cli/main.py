"""NeuralClaw CLI - Single-file main with all commands."""

import json
import time
import uuid
import typer
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm, Prompt

from neuralclaw.db.connection import (
    init_db, db_exists, get_config_dir, get_schema_version,
    get_vault_dir, get_vault_key_path, get_connection
)
from neuralclaw.core.vault import (
    vault_set, vault_get, vault_list, vault_delete, vault_exists, init_vault
)
from neuralclaw.core.context import (
    add_context_item, search_context, get_context_item,
    update_context_item_state, delete_context_item, count_context_items
)
from neuralclaw.core.projects import (
    create_project, list_projects, get_project,
    archive_project, delete_project, project_exists
)
from neuralclaw.core.bridge import export_context_json, load_adapter

# Main app
app = typer.Typer(
    name="neuralclaw",
    help="NeuralClaw — Local Context OS for AI Agents",
    add_completion=False,
)

# Sub-groups
project_app = typer.Typer(name="project", help="Manage projects")
vault_app = typer.Typer(name="vault", help="Manage encrypted secrets")

app.add_typer(project_app)
app.add_typer(vault_app)

console = Console()


# ─── INIT ───────────────────────────────────────────────────────────────────────

@app.command()
def init():
    """Initialize NeuralClaw: creates config, database, and vault."""
    config_dir = get_config_dir()
    console.print(f"[bold]Initializing NeuralClaw at:[/bold] {config_dir}")

    if db_exists():
        version = get_schema_version()
        console.print(f"[yellow]Database already exists (schema v{version})[/yellow]")
    else:
        init_db()
        console.print("[green]✓[/green] Database created")

    if vault_exists():
        console.print("[yellow]Vault already initialized[/yellow]")
    else:
        init_vault()
        console.print("[green]✓[/green] Vault initialized")

    console.print(f"\n[bold green]NeuralClaw ready![/bold green]")
    console.print(f"Config: {config_dir}")
    console.print("\nNext: neuralclaw add 'my_key=my_value' --project my-project")


# ─── ADD ──────────────────────────────────────────────────────────────────────

@app.command()
def add(
    item: str = typer.Argument(..., help="Context item as 'key=value' or 'key:value' format"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name or ID"),
    item_type: str = typer.Option("note", "--type", "-t", help="Type: note, decision, error, variable, preference"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
    stale_after: Optional[int] = typer.Option(None, "--stale-after", help="Unix timestamp after which item is stale"),
    confidence: float = typer.Option(1.0, "--confidence", help="Confidence 0.0-1.0"),
    state: str = typer.Option("active", "--state", "-s", help="State: active, stale, verified, deprecated, archived, conflicting"),
):
    """Add a context item."""
    if "=" in item:
        key, value = item.split("=", 1)
    elif ":" in item:
        key, value = item.split(":", 1)
    else:
        console.print("[red]Error:[/red] Item must be 'key=value' or 'key:value' format")
        raise typer.Exit(1)

    key, value = key.strip(), value.strip()

    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found. Use 'neuralclaw project create' first.")
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    item_id = add_context_item(
        project_id=project_id, key=key, value=value,
        item_type=item_type, state=state, tags=tag_list,
        stale_after=stale_after, confidence=confidence,
    )

    console.print(f"[green]✓[/green] Added context item [bold]{key}[/bold]")
    console.print(f"  ID: {item_id}")
    if project:
        console.print(f"  Project: {project}")
    console.print(f"  Type: {item_type} | State: {state}")
    if tag_list:
        console.print(f"  Tags: {', '.join(tag_list)}")


# ─── SEARCH ───────────────────────────────────────────────────────────────────

@app.command()
def search(
    query: str = typer.Argument("", help="Search query (optional)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project name or ID"),
    state: Optional[str] = typer.Option(None, "--state", "-s", help="Filter by state"),
    item_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Filter by comma-separated tags"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Search context items."""
    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    results = search_context(
        query=query or None, project_id=project_id,
        state=state, item_type=item_type, tags=tag_list, limit=limit,
    )

    if json_output:
        console.print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if not results:
        console.print("[dim]No results found[/dim]")
        return

    table = Table(title=f"Context Items ({len(results)} results)")
    table.add_column("Key", style="cyan", no_wrap=False)
    table.add_column("Value", style="white", no_wrap=False)
    table.add_column("Type", style="magenta")
    table.add_column("State", style="green")
    table.add_column("Tags", style="dim")

    for r in results:
        tags_str = ", ".join(r["tags"]) if r["tags"] else "-"
        value_short = r["value"][:50] + "..." if len(r["value"]) > 50 else r["value"]
        table.add_row(r["key"], value_short, r["type"], r["state"], tags_str)

    console.print(table)


# ─── CONTEXT ────────────────────────────────────────────────────────────────────

@app.command()
def context(
    task: str = typer.Option("", "--task", "-t", help="Task description for context"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name or ID"),
    adapter: str = typer.Option("openclaw", "--adapter", "-a", help="Adapter: openclaw, chatgpt, claude"),
    include_vars: bool = typer.Option(False, "--include-vars", help="Reveal vault variable values"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Search query to filter context"),
    json_output: bool = typer.Option(True, "--json", help="Output as JSON"),
):
    """Export context as JSON for an AI agent."""
    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    try:
        json_str = export_context_json(
            task=task, project_id=project_id,
            adapter_name=adapter, include_vars=include_vars, query=query,
        )
        console.print(json_str)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ─── PROJECT SUB-GROUP ─────────────────────────────────────────────────────────

@project_app.command(name="create")
def project_create(
    name: str = typer.Argument(..., help="Project name"),
    description: str = typer.Option("", "--description", "-d", help="Project description"),
):
    """Create a new project."""
    try:
        project_id = create_project(name, description)
        console.print(f"[green]✓[/green] Project [bold]{name}[/bold] created")
        console.print(f"  ID: {project_id}")
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            console.print(f"[red]Error:[/red] Project '{name}' already exists.")
        else:
            raise


@project_app.command(name="list")
def project_list(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter: active, archived"),
):
    """List all projects."""
    projects = list_projects(status=status)
    if not projects:
        console.print("[dim]No projects found[/dim]")
        return

    table = Table(title="Projects")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Description", style="white")
    table.add_column("Created", style="dim")

    for p in projects:
        created = datetime.fromtimestamp(p["created_at"]).strftime("%Y-%m-%d")
        table.add_row(p["name"], p["status"], p["description"] or "-", created)
    console.print(table)


@project_app.command(name="archive")
def project_archive(name: str = typer.Argument(..., help="Project name or ID")):
    """Archive a project."""
    project = get_project(name)
    if not project:
        console.print(f"[red]Error:[/red] Project '{name}' not found.")
        raise typer.Exit(1)
    if project["status"] == "archived":
        console.print(f"[yellow]Project '{project['name']}' is already archived[/yellow]")
        return
    archive_project(project["id"])
    console.print(f"[green]✓[/green] Project [bold]{project['name']}[/bold] archived")


@project_app.command(name="delete")
def project_delete(
    name: str = typer.Argument(..., help="Project name or ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a project and all its context items."""
    project = get_project(name)
    if not project:
        console.print(f"[red]Error:[/red] Project '{name}' not found.")
        raise typer.Exit(1)
    if not force and not Confirm.ask(f"Delete project [bold]{project['name']}[/bold] and ALL its context items?"):
        console.print("[yellow]Cancelled[/yellow]")
        return
    delete_project(project["id"])
    console.print(f"[green]✓[/green] Project [bold]{project['name']}[/bold] deleted")


@project_app.command(name="status")
def project_status(name: str = typer.Argument(..., help="Project name or ID")):
    """Show project status."""
    project = get_project(name)
    if not project:
        console.print(f"[red]Error:[/red] Project '{name}' not found.")
        raise typer.Exit(1)

    total = count_context_items(project_id=project["id"])
    active = count_context_items(project_id=project["id"], state="active")
    stale = count_context_items(project_id=project["id"], state="stale")

    console.print(f"\n[bold]{project['name']}[/bold]")
    console.print(f"  Status: {project['status']}")
    console.print(f"  Created: {datetime.fromtimestamp(project['created_at']).strftime('%Y-%m-%d %H:%M')}")
    console.print(f"  Context items: {total} (active={active}, stale={stale})")
    if project.get("description"):
        console.print(f"  Description: {project['description']}")


# ─── VAULT SUB-GROUP ──────────────────────────────────────────────────────────

@vault_app.command(name="set")
def vault_set_cmd(
    name: str = typer.Argument(..., help="Secret name (e.g. OPENAI_API_KEY)"),
    value: Optional[str] = typer.Argument(None, help="Secret value (will prompt if not provided)"),
):
    """Store a secret in the vault."""
    if not value:
        value = Prompt.ask(f"Enter value for [bold]{name}[/bold]", password=True)
    vault_set(name.upper(), value)
    console.print(f"[green]✓[/green] Secret [bold]{name.upper()}[/bold] stored")


@vault_app.command(name="get")
def vault_get_cmd(
    name: str = typer.Argument(..., help="Secret name"),
    reveal: bool = typer.Option(False, "--reveal", help="Show the actual value"),
):
    """Retrieve a secret from the vault."""
    val = vault_get(name.upper())
    if val is None:
        console.print(f"[red]Error:[/red] Secret '{name}' not found.")
        raise typer.Exit(1)
    if reveal:
        console.print(f"[bold]{name.upper()}[/bold] = {val}")
    else:
        console.print(f"[bold]{name.upper()}[/bold] is set (use --reveal to show value)")


@vault_app.command(name="list")
def vault_list_cmd():
    """List all secrets (names only)."""
    if not vault_exists():
        console.print("[dim]Vault not initialized[/dim]")
        return
    secrets = vault_list()
    if not secrets:
        console.print("[dim]No secrets stored[/dim]")
        return
    table = Table(title="Vault Secrets")
    table.add_column("Name", style="cyan")
    for name in secrets:
        table.add_row(name)
    console.print(table)


@vault_app.command(name="delete")
def vault_delete_cmd(
    name: str = typer.Argument(..., help="Secret name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a secret from the vault."""
    if not vault_exists() or vault_get(name.upper()) is None:
        console.print(f"[red]Error:[/red] Secret '{name}' not found.")
        raise typer.Exit(1)
    if not force and not Confirm.ask(f"Delete secret [bold]{name.upper()}[/bold]?"):
        console.print("[yellow]Cancelled[/yellow]")
        return
    vault_delete(name.upper())
    console.print(f"[green]✓[/green] Secret [bold]{name.upper()}[/bold] deleted")


@vault_app.command(name="status")
def vault_status_cmd():
    """Show vault status."""
    if not vault_exists():
        console.print("[yellow]Vault not initialized (run 'neuralclaw init')[/yellow]")
        return
    secrets = vault_list()
    console.print(f"[green]✓[/green] Vault initialized")
    console.print(f"  Secrets stored: {len(secrets)}")


# ─── MAIN ──────────────────────────────────────────────────────────────────────

@app.callback()
def callback():
    """NeuralClaw - Local Context OS for AI Agents."""
    pass


if __name__ == "__main__":
    app()
