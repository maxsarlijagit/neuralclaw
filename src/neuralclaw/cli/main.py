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
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from neuralclaw.db.connection import (
    init_db, db_exists, get_config_dir, get_schema_version,
    get_vault_dir, get_vault_key_path, get_connection
)
from neuralclaw.core.vault import (
    vault_set, vault_get, vault_list, vault_delete, vault_exists, init_vault
)
from neuralclaw.core.context import (
    add_context_item, get_context_item, bulk_import_context, get_all_items,
    update_context_item_state, delete_context_item, count_context_items
)
from neuralclaw.core.search import search_context_smart, suggest_context
from neuralclaw.core.projects import (
    create_project, list_projects, get_project,
    archive_project, delete_project, project_exists
)
from neuralclaw.core.bridge import export_context_json, load_adapter
from neuralclaw.plugins import (
    load_plugins, list_plugins, enable_plugin, disable_plugin, get_plugin,
    run_context_search_hooks, run_context_export_hooks,
)
from neuralclaw.core.train_room import (
    analyze_and_save_profile, load_profile, list_profiles, PROFILES_DIR
)
from neuralclaw.core.playroom import test_prompt, print_comparison
from neuralclaw.core.fresh import (
    generate_fresh_apple, save_fresh_apple, get_fresh_apple,
    is_fresh, list_fresh_apples
)
from neuralclaw.core.doctor import run_doctor_checks, print_doctor_report
from neuralclaw.logging import init_logging, log_command


# Main app
app = typer.Typer(
    name="neuralclaw",
    help="NeuralClaw — Local Context OS for AI Agents",
    add_completion=False,
    invoke_without_command=True,
)

# Version from pyproject.toml
__version__ = "0.4.1"

# Sub-groups
project_app = typer.Typer(name="project", help="Manage projects")
vault_app = typer.Typer(name="vault", help="Manage encrypted secrets")
plugin_app = typer.Typer(name="plugin", help="Manage plugins")
train_room_app = typer.Typer(name="train-room", help="Train Room — analyze samples and generate profiles")
playroom_app = typer.Typer(name="playroom", help="Playroom — test adapters side-by-side")

app.add_typer(project_app)
app.add_typer(vault_app)
app.add_typer(plugin_app)
app.add_typer(train_room_app)
app.add_typer(playroom_app)

console = Console()


# ─── AUTO SETUP ───────────────────────────────────────────────────────────────

def _auto_setup():
    """Auto-create default project if DB exists but has no projects.
    
    Called on startup to ensure the CLI always works without manual setup.
    """
    if not db_exists():
        return  # No DB yet, init will handle
    
    if not vault_exists():
        return  # Vault not initialized
    
    # DB exists, check for projects
    try:
        from neuralclaw.core.projects import list_projects
        projects = list_projects()
        
        if len(projects) == 0:
            # Auto-create default project silently
            from neuralclaw.core.projects import create_project
            create_project("default", "Default project created automatically")
    except Exception:
        pass  # Fail silently - not critical


# ─── MAIN CALLBACK (--version) ────────────────────────────────────────────────

@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
):
    """NeuralClaw — Local Context OS for AI Agents."""
    if version:
        console.print(f"[cyan]NeuralClaw[/cyan] [bold]{__version__}[/bold]")
        raise typer.Exit()


# ─── VERSION SUB_COMMAND ──────────────────────────────────────────────────────

@app.command(name="version")
def version():
    """Show NeuralClaw version."""
    console.print(f"[cyan]NeuralClaw[/cyan] version [bold]{__version__}[/bold]")

@app.command()
def tui():
    """Launch the interactive TUI (Text User Interface)."""
    try:
        from neuralclaw.ui.tui import run_tui
        run_tui()
    except ImportError:
        console.print("[red]Error:[/red] Rich library required for TUI. Install with: pip install rich")
        raise typer.Exit(1)


@app.command()
def serve(
    port: int = typer.Option(7890, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
):
    """Start the FastAPI REST API server with web dashboard."""
    try:
        from neuralclaw.api.server import run_server
        console.print(f"[green]Starting NeuralClaw API server...[/green]")
        console.print(f"  Dashboard: http://localhost:{port}/")
        console.print(f"  API docs:  http://localhost:{port}/docs")
        run_server(host=host, port=port)
    except ImportError:
        console.print("[red]Error:[/red] FastAPI and uvicorn required. Install with: pip install fastapi uvicorn")
        raise typer.Exit(1)




# ─── INIT ───────────────────────────────────────────────────────────────────────

@app.command()
def init(
    non_interactive: bool = typer.Option(False, "--yes", "-y", help="Skip interactive prompts (for automation)")
):
    """Initialize NeuralClaw with an interactive setup wizard.
    
    Creates config directory, database, vault, and optionally
    guides you through creating your first project and selecting adapters.
    """
    # Check if already initialized (not first run)
    already_init = db_exists() and vault_exists()
    
    if already_init:
        version = get_schema_version()
        console.print(f"[yellow]NeuralClaw already initialized (schema v{version})[/yellow]")
        if non_interactive:
            console.print("[dim]Skipping. Run without -y to re-run setup wizard.[/dim]")
            return
        if not Confirm.ask("[dim]Re-run setup wizard?[/dim]", default=False):
            console.print("[dim]Skipping. Your config is intact.[/dim]")
            return
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: Welcome
    # ═══════════════════════════════════════════════════════════════════════
    console.print(Panel.fit(
        "[bold cyan]🤖 NeuralClaw First Run Setup[/bold cyan]\n\n"
        "[dim]Local Context OS for AI Agents[/dim]",
        border_style="cyan"
    ))
    console.print()
    
    if not non_interactive:
        console.print("[dim]This wizard will:[/dim]")
        console.print("  • Create your config directory (~/.config/neuralclaw/)")
        console.print("  • Initialize the SQLite database")
        console.print("  • Set up the encrypted vault")
        console.print("  • Help you create your first project")
        console.print()
        if not Confirm.ask("[cyan]Press ENTER to start setup...[/cyan]", default=True):
            console.print("[dim]Cancelled.[/dim]")
            return
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: Initialize database and vault
    # ═══════════════════════════════════════════════════════════════════════
    console.print(Panel.fit(
        "[bold]Step 1: System Initialization[/bold]",
        border_style="green"
    ))
    
    config_dir = get_config_dir()
    console.print(f"\n[dim]Config directory:[/dim] [cyan]{config_dir}[/cyan]")
    
    # Init database
    if not db_exists():
        init_db()
        console.print("[green]✓[/green] Database created")
    else:
        version = get_schema_version()
        console.print(f"[yellow]✓[/yellow] Database exists (v{version})")
    
    # Init vault
    if not vault_exists():
        init_vault()
        console.print("[green]✓[/green] Vault initialized (secrets encrypted)")
    else:
        console.print("[yellow]✓[/yellow] Vault already exists")
    
    console.print()
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: Auto-Setup Projects
    # ═══════════════════════════════════════════════════════════════════════
    console.print(Panel.fit(
        "[bold]Step 2: Auto-Setup Projects[/bold]",
        border_style="green"
    ))
    console.print("[dim]Checking for existing projects...[/dim]\n")
    
    # Auto-setup: scan existing projects and auto-create default if needed
    existing_projects = []
    try:
        from neuralclaw.core.projects import list_projects
        existing_projects = list_projects()
    except Exception:
        pass
    
    if len(existing_projects) == 0:
        console.print("[cyan]→[/cyan] No projects found. Creating 'default' project automatically...")
        try:
            from neuralclaw.core.projects import create_project
            create_project("default", "Default project created automatically on first setup")
            console.print("[green]✓[/green] Project 'default' created")
        except Exception as e:
            console.print(f"[yellow]![/yellow] Could not auto-create project: {e}")
    else:
        project_names = [p["name"] for p in existing_projects]
        console.print(f"[green]✓[/green] Found {len(existing_projects)} project(s): [cyan]{', '.join(project_names)}[/cyan]")
    
    console.print()
    
    console.print()
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 4: Adapter selection
    # ═══════════════════════════════════════════════════════════════════════
    console.print(Panel.fit(
        "[bold]Step 3: AI Adapters[/bold]",
        border_style="green"
    ))
    console.print("[dim]Select the AI systems you work with:[/dim]\n")
    
    if non_interactive:
        enabled_adapters = ["openclaw", "claude", "chatgpt"]
    else:
        console.print("  [dim](Press SPACE to toggle, ENTER to confirm)[/dim]")
        console.print()
        
        # Use default selections
        adapters_available = [
            ("openclaw", "OpenClaw — Local agent framework"),
            ("claude", "Claude — Anthropic's Claude"),
            ("chatgpt", "ChatGPT — OpenAI"),
        ]
        
        enabled_adapters = []
        for adapter_id, adapter_desc in adapters_available:
            console.print(f"    [cyan]•[/cyan] {adapter_desc}")
        
        console.print()
        console.print("[dim]All adapters enabled by default. Run 'neuralclaw config' to change later.[/dim]")
        enabled_adapters = [a[0] for a in adapters_available]
    
    console.print()
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 5: Ollama (optional)
    # ═══════════════════════════════════════════════════════════════════════
    console.print(Panel.fit(
        "[bold]Step 4: Ollama Integration (Optional)[/bold]",
        border_style="yellow"
    ))
    console.print("[dim]Ollama enables semantic search via local embeddings.[/dim]\n")
    
    if non_interactive:
        enable_ollama = False
    else:
        enable_ollama = Confirm.ask(
            "[cyan]Enable Ollama for semantic search?[/cyan]",
            default=False
        )
        
        if enable_ollama:
            console.print("[dim]  → Set OLLAMA_URL in your environment or run 'neuralclaw config'[/dim]")
    
    console.print()
    
    # ═══════════════════════════════════════════════════════════════════════
    # COMPLETION
    # ═══════════════════════════════════════════════════════════════════════
    console.print(Panel.fit(
        "[bold green]✅ NeuralClaw Setup Complete![/bold green]",
        border_style="green"
    ))
    console.print()
    
    # Summary
    from neuralclaw.core.projects import list_projects
    projects = list_projects()
    
    summary_lines = [
        f"[dim]Config:[/dim]     {config_dir}",
        f"[dim]Database:[/dim]    SQLite (local)",
        f"[dim]Vault:[/dim]       Encrypted with Fernet",
        f"[dim]Projects:[/dim]   {len(projects)} created",
        f"[dim]Adapters:[/dim]    {', '.join(enabled_adapters)}",
    ]
    
    for line in summary_lines:
        console.print(f"  {line}")
    
    console.print()
    console.print("[bold]Quick start:[/bold]")
    console.print("  [cyan]neuralclaw add[/cyan] 'my_key=my_value' --project my-first-project")
    console.print("  [cyan]neuralclaw project list[/cyan]")
    console.print("  [cyan]neuralclaw --help[/cyan]")
    console.print()


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
    offset: int = typer.Option(0, "--offset", "-o", help="Pagination offset"),
    method: str = typer.Option("auto", "--method", "-m", help="Search method: auto, keyword, fts, embeddings"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    use_fts: bool = typer.Option(False, "--use-fts", help="Force FTS5 full-text search"),
):
    """Search context items."""
    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    # Normalize method
    if use_fts:
        search_method = "fts"
    elif method == "auto":
        search_method = "auto"
    else:
        search_method = method

    results = search_context_smart(
        query=query or None, project_id=project_id,
        state=state, item_type=item_type, tags=tag_list, limit=limit, offset=offset,
        method=search_method,
    )

    # Run plugin hooks on search results
    results = run_context_search_hooks(query=query or None, project_id=project_id, results=results)

    if json_output:
        console.print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if not results:
        if offset > 0:
            console.print(f"[dim]No more results (page offset: {offset})[/dim]")
        else:
            console.print("[dim]No results found[/dim]")
        return

    if offset > 0:
        console.print(f"[dim]Showing results {offset} to {offset + len(results)}[/dim]")

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
        # Run plugin export hooks on the JSON string
        if json_output:
            import json as _json
            export_data = _json.loads(json_str)
            export_data = run_context_export_hooks(export_data)
            json_str = _json.dumps(export_data, indent=2, ensure_ascii=False)
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


# ─── FRESH ───────────────────────────────────────────────────────────────────

@app.command()
def fresh(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name or ID"),
    regenerate: bool = typer.Option(False, "--regenerate", "-r", help="Force regenerate FreshApple snapshot"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save to DB (default: save)"),
    ttl: int = typer.Option(3600, "--ttl", help="Freshness TTL in seconds (default: 3600 = 1h)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON with metadata"),
):
    """Generate or display a FreshApple snapshot for a project.

    FreshApple = markdown snapshot of active context including projects,
    next steps, risks, recent errors, and key context.

    Auto-refresh: if --regenerate is not set, returns cached snapshot if fresh (within TTL).
    """
    project_id = None
    project_name = None

    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            raise typer.Exit(1)
        proj = get_project(project)
        project_id = proj["id"]
        project_name = proj["name"]

    # Check cache unless regenerating
    if not regenerate and project_id:
        if is_fresh(project_id, ttl_seconds=ttl):
            fa = get_fresh_apple(project_id)
            if fa:
                console.print(f"[dim]FreshApple cached (fresh for {ttl}s)[/dim]")
                if json_output:
                    import json
                    console.print(json.dumps({
                        "source": "cached",
                        "generated_at": fa["generated_at"],
                        "content": fa["content"],
                        "project_id": project_id,
                    }, indent=2))
                else:
                    console.print(fa["content"])
                return

    # Generate fresh snapshot
    content = generate_fresh_apple(project_id=project_id, project_name=project_name)
    generated_at = int(time.time())

    if save:
        saved_id = save_fresh_apple(project_id, content, auto_refresh=True)
        if saved_id:
            console.print(f"[green]✓[/green] FreshApple saved to DB (ID: {saved_id[:8]}...)")
        else:
            console.print("[dim]FreshApple generated (global context — not persisted)[/dim]")

    if json_output:
        import json
        console.print(json.dumps({
            "source": "generated",
            "generated_at": generated_at,
            "content": content,
            "project_id": project_id,
        }, indent=2))
    else:
        console.print(content)


# ─── IMPORT ────────────────────────────────────────────────────────────────────

@app.command()
def import_cmd(
    from_file: str = typer.Option(..., "--from", "-f", help="Input file (JSON or JSONL)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Default project for items"),
    batch_size: int = typer.Option(100, "--batch-size", help="Batch size for bulk insert"),
):
    """Bulk import context items from a JSON or JSONL file."""
    from neuralclaw.logging import log_command, log_info

    input_path = Path(from_file)
    if not input_path.exists():
        console.print(f"[red]Error:[/red] File not found: {input_path}")
        raise typer.Exit(1)

    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    try:
        content = input_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        console.print(f"[red]Error:[/red] Could not read file: {e}")
        raise typer.Exit(1)

    # Detect format: JSONL if lines, JSON if array
    items = []
    if content.startswith("["):
        # JSON array
        try:
            items = json.loads(content)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error:[/red] Invalid JSON: {e}")
            raise typer.Exit(1)
    else:
        # JSONL (newline-delimited JSON)
        for i, line in enumerate(content.split("\n")):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                console.print(f"[red]Error:[/red] Invalid JSON on line {i+1}: {e}")
                raise typer.Exit(1)

    if not items:
        console.print("[yellow]No items found in file[/yellow]")
        return

    console.print(f"[cyan]Importing {len(items)} items...[/cyan]")

    # Batch insert
    added = 0
    errors = 0
    with log_command("import", project_id=project_id):
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            for item_data in batch:
                key = item_data.get("key") or item_data.get("KEY")
                value = item_data.get("value") or item_data.get("VALUE") or item_data.get("v")
                if not key or value is None:
                    errors += 1
                    continue
                try:
                    add_context_item(
                        project_id=item_data.get("project_id") or project_id,
                        key=str(key),
                        value=str(value),
                        item_type=item_data.get("type") or item_data.get("item_type") or "note",
                        state=item_data.get("state") or "active",
                        tags=item_data.get("tags") or [],
                        sources=item_data.get("sources") or [],
                        stale_after=item_data.get("stale_after"),
                        confidence=item_data.get("confidence", 1.0),
                    )
                    added += 1
                except Exception:
                    errors += 1

    log_info(f"Imported {added} items ({errors} errors)")
    console.print(f"[green]✓[/green] Imported [bold]{added}[/bold] items")
    if errors > 0:
        console.print(f"[yellow]⚠ {errors} items skipped (missing key/value)[/yellow]")


# ─── BACKUP & RESTORE ─────────────────────────────────────────────────────────

@app.command(name="backup")
def backup_cmd(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (.json or .json.gz)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Backup specific project"),
    pretty: bool = typer.Option(True, "--pretty/--no-pretty", help="Human-readable JSON"),
):
    """Export all context items, projects, and vault entries as JSON backup.
    
    Creates a portable backup file that can be restored with:
    neuralclaw restore --from backup.json
    """
    import gzip
    from pathlib import Path
    
    # Get all projects
    projects = list_projects()
    
    # Get context items
    project_id = None
    if project:
        proj = get_project(project)
        if not proj:
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            raise typer.Exit(1)
        project_id = proj["id"]
    
    context_items = get_all_items(project_id=project_id)
    
    # Get vault entries (metadata only, not values — values stay in vault)
    vault_entries = []
    if vault_exists():
        from neuralclaw.core.vault import vault_list
        vault_entries = vault_list()  # [{name, type, created_at}]
    
    # Build backup structure
    backup = {
        "version": "0.4.1",
        "exported_at": datetime.now().isoformat(),
        "projects": projects,
        "context_items": context_items,
        "vault_metadata": vault_entries,  # names/types only, no values
        "schema_version": get_schema_version(),
    }
    
    # Determine output
    if not output:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"neuralclaw_backup_{ts}.json"
    
    output_path = Path(output).expanduser()
    
    # Write backup
    if str(output).endswith(".gz"):
        with gzip.open(output_path, "wt", encoding="utf-8") as f:
            json.dump(backup, f, indent=2 if pretty else None)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(backup, f, indent=2 if pretty else None)
    
    console.print(f"[green]✓[/green] Backup saved to [bold]{output_path}[/bold]")
    console.print(f"  Projects: {len(projects)}")
    console.print(f"  Context items: {len(context_items)}")
    console.print(f"  Vault entries: {len(vault_entries)}")
    console.print("\n[dim]Note: Vault values are NOT exported (security). Run 'neuralclaw vault export' separately for secrets.")


@app.command(name="restore")
def restore_cmd(
    from_file: str = typer.Argument(..., help="Backup file to restore (.json or .json.gz)"),
    merge: bool = typer.Option(True, "--merge/--replace", help="Merge with existing data or replace"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Restore context items and projects from a backup file.
    
    Usage:
    neuralclaw restore backup_20260427.json
    """
    import gzip
    from pathlib import Path
    
    backup_path = Path(from_file).expanduser()
    if not backup_path.exists():
        console.print(f"[red]Error:[/red] Backup file not found: {from_file}")
        raise typer.Exit(1)
    
    # Load backup
    try:
        if str(from_file).endswith(".gz"):
            with gzip.open(backup_path, "rt", encoding="utf-8") as f:
                backup = json.load(f)
        else:
            with open(backup_path, "r", encoding="utf-8") as f:
                backup = json.load(f)
    except Exception as e:
        console.print(f"[red]Error:[/red] Could not read backup file: {e}")
        raise typer.Exit(1)
    
    # Validate backup structure
    if "context_items" not in backup:
        console.print("[red]Error:[/red] Invalid backup file (missing context_items)")
        raise typer.Exit(1)
    
    if not force and not merge:
        console.print("[yellow]⚠ This will replace ALL existing data![/yellow]")
        if not Confirm.ask("Continue?"):
            console.print("[dim]Cancelled[/dim]")
            return
    elif not force and merge:
        console.print(f"[cyan]→[/cyan] Merging {len(backup['context_items'])} items into existing data")
        if not Confirm.ask("Continue?", default=True):
            return
    
    # Restore projects
    projects_restored = 0
    for proj in backup.get("projects", []):
        if not project_exists(proj["name"]):
            create_project(proj["name"], proj.get("description", ""))
            projects_restored += 1
    
    # Restore context items
    items_restored = 0
    for item in backup["context_items"]:
        try:
            proj_id = item.get("project_id")
            if proj_id:
                proj = get_project(proj_id)
                if not proj:
                    # Project not found, skip
                    continue
            add_context_item(
                project_id=proj_id,
                key=item["key"],
                value=item["value"],
                item_type=item.get("type", "note"),
                state=item.get("state", "active"),
                tags=item.get("tags", []),
                sources=item.get("sources", []),
                stale_after=item.get("stale_after"),
                confidence=item.get("confidence", 1.0),
            )
            items_restored += 1
        except Exception:
            pass
    
    console.print(f"[green]✓[/green] Restore complete")
    console.print(f"  Projects created: {projects_restored}")
    console.print(f"  Context items restored: {items_restored}")


# ─── DELETE CONTEXT ITEM ──────────────────────────────────────────────────────

@app.command(name="delete")
def delete_item_cmd(
    item_id: str = typer.Argument(..., help="Context item ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a context item by ID.
    
    Use 'neuralclaw search' to find item IDs first.
    """
    item = get_context_item(item_id)
    if not item:
        console.print(f"[red]Error:[/red] Item not found: {item_id}")
        raise typer.Exit(1)
    
    console.print(f"[cyan]Item details:[/cyan]")
    console.print(f"  Key: [bold]{item['key']}[/bold]")
    console.print(f"  Value: {item.get('value', '')[:60]}...")
    console.print(f"  Type: {item.get('type', 'note')} | State: {item.get('state', 'active')}")
    if item.get('project_id'):
        console.print(f"  Project: {item['project_id']}")
    
    if not force and not Confirm.ask(f"\nDelete this item?"):
        console.print("[yellow]Cancelled[/yellow]")
        return
    
    success = delete_context_item(item_id)
    if success:
        console.print(f"[green]✓[/green] Item deleted")
    else:
        console.print(f"[red]Error:[/red] Could not delete item")
        raise typer.Exit(1)


# ─── DOCTOR ─────────────────────────────────────────────────────────────────

@app.command()
def doctor():
    """Run health checks on the NeuralClaw system.

    Checks:
    - DB accessible + schema correct
    - Vault.key exists
    - FreshApple snapshots fresh (warn if >7 days old)
    - Items stale >7 days without refresh
    - Conflicts unresolved (state='conflicting')
    - usage_logs empty for 30+ days → warning
    """
    results, pass_count, total = run_doctor_checks()
    print_doctor_report(results, pass_count, total)


# ─── PLUGIN SUB-GROUP ─────────────────────────────────────────────────────────

@plugin_app.command(name="list")
def plugin_list():
    """List all loaded plugins with their status."""
    plugins = load_plugins()
    if not plugins:
        console.print("[dim]No plugins loaded[/dim]")
        return

    table = Table(title=f"Plugins ({len(plugins)} loaded)")
    table.add_column("Name", style="cyan")
    table.add_column("Module", style="dim")
    table.add_column("Hooks", style="yellow")
    table.add_column("Enabled", style="green")

    for spec in list_plugins():
        hook_names = [k for k in spec.hooks.keys()]
        enabled_str = "[green]✓ enabled[/green]" if spec.enabled else "[red]✗ disabled[/red]"
        table.add_row(spec.name, spec.module_name, ", ".join(hook_names), enabled_str)

    console.print(table)


@plugin_app.command(name="enable")
def plugin_enable(name: str = typer.Argument(..., help="Plugin name")):
    """Enable a plugin by name."""
    if not get_plugin(name):
        console.print(f"[red]Error:[/red] Plugin '{name}' not found.")
        raise typer.Exit(1)
    if enable_plugin(name):
        console.print(f"[green]✓[/green] Plugin [bold]{name}[/bold] enabled")
    else:
        console.print(f"[red]Error:[/red] Could not enable plugin '{name}'.")
        raise typer.Exit(1)


@plugin_app.command(name="disable")
def plugin_disable(name: str = typer.Argument(..., help="Plugin name")):
    """Disable a plugin by name."""
    if not get_plugin(name):
        console.print(f"[red]Error:[/red] Plugin '{name}' not found.")
        raise typer.Exit(1)
    if disable_plugin(name):
        console.print(f"[green]✓[/green] Plugin [bold]{name}[/bold] disabled")
    else:
        console.print(f"[red]Error:[/red] Could not disable plugin '{name}'.")
        raise typer.Exit(1)


@plugin_app.command(name="info")
def plugin_info(name: str = typer.Argument(..., help="Plugin name")):
    """Show detailed info about a plugin."""
    if not get_plugin(name):
        console.print(f"[red]Error:[/red] Plugin '{name}' not found.")
        raise typer.Exit(1)
    spec = get_plugin(name)
    console.print(f"\n[bold]{spec.name}[/bold]")
    console.print(f"  Module: {spec.module_name}")
    console.print(f"  Status: {'enabled' if spec.enabled else 'disabled'}")
    console.print(f"  Hooks: {', '.join(spec.hooks.keys()) or '(none)'}")


# ─── TRAIN ROOM SUB-GROUP ─────────────────────────────────────────────────────

@train_room_app.command(name="analyze")
def train_room_analyze(
    samples: str = typer.Option(..., "--samples", "-s", help="Path to samples directory or file"),
    model: str = typer.Option(..., "--model", "-m", help="Model ID to save profile under"),
):
    """Analyze conversation samples and generate a communication profile."""
    from pathlib import Path
    samples_path = Path(samples)
    if not samples_path.exists():
        console.print(f"[red]Error:[/red] Samples path not found: {samples}")
        raise typer.Exit(1)

    console.print(f"[cyan]Analyzing samples from:[/cyan] {samples_path}")
    try:
        profile = analyze_and_save_profile(samples_path, model)
        console.print(f"\n[green]✓[/green] Profile saved for [bold]{model}[/bold]")
        console.print(f"  Communication style: {profile['communication_style']}")
        console.print(f"  Preferred length: {profile['preferred_length']}")
        console.print(f"  Format preference: {profile['format_preference']}")
        console.print(f"  Tone: {profile['tone']}")
        stats = profile.get("analysis_stats", {})
        console.print(f"\n  Stats: {stats.get('total_samples', 0)} samples, "
                      f"avg {stats.get('avg_response_length', 0):.0f} words")
        console.print(f"  Profile saved to: {PROFILES_DIR / f'{model}.json'}")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


@train_room_app.command(name="generate")
def train_room_generate(
    model: str = typer.Option(..., "--model", "-m", help="Model ID"),
):
    """Show or regenerate a saved profile for a model."""
    profile = load_profile(model)
    if not profile:
        console.print(f"[red]Error:[/red] No profile found for '{model}'.")
        console.print(f"  Run: neuralclaw train-room analyze --samples /path --model {model}")
        raise typer.Exit(1)
    console.print(json.dumps(profile, indent=2, ensure_ascii=False))


@train_room_app.command(name="list")
def train_room_list():
    """List all saved model profiles."""
    profiles = list_profiles()
    if not profiles:
        console.print("[dim]No profiles saved yet. Run 'train-room analyze' first.[/dim]")
        return
    table = Table(title=f"Model Profiles ({len(profiles)})")
    table.add_column("Model ID", style="cyan")
    table.add_column("Style", style="magenta")
    table.add_column("Length", style="yellow")
    table.add_column("Format", style="green")
    table.add_column("Tone", style="blue")
    for p in profiles:
        table.add_row(
            p.get("model_id", "?"),
            p.get("communication_style", "?"),
            p.get("preferred_length", "?"),
            p.get("format_preference", "?"),
            p.get("tone", "?"),
        )
    console.print(table)


# ─── PLAYROOM SUB-GROUP ───────────────────────────────────────────────────────

@playroom_app.command(name="test")
def playroom_test(
    prompt: str = typer.Argument(..., help="Prompt to test across adapters"),
    adapter: str = typer.Option("openclaw,chatgpt,claude", "--adapter", "-a", help="Comma-separated adapter names"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name or ID"),
):
    """Test a prompt across multiple adapters and compare outputs."""
    adapter_names = [a.strip() for a in adapter.split(",") if a.strip()]
    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    console.print(f"[cyan]Testing prompt across:[/cyan] {', '.join(adapter_names)}\n")
    try:
        result = test_prompt(prompt, adapter_names, project_id=project_id)
        print_comparison(result)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


# ─── SUGGEST ──────────────────────────────────────────────────────────────────

@app.command()
def suggest(
    query: str = typer.Argument(..., help="Partial context description to find related items"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project name or ID"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max suggestions"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Find context items related to a partial description using semantic search.

    Requires Ollama to be running with an embeddings model (e.g. mxbai-embed-large).
    Falls back to keyword search if Ollama is unavailable.
    """
    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    results = suggest_context(query=query, project_id=project_id, limit=limit)

    if not results:
        # Fall back to keyword search if embeddings unavailable
        from neuralclaw.core.search import search_context_keyword
        results = search_context_keyword(
            query=query,
            project_id=project_id,
            limit=limit,
        )
        if results:
            console.print("[dim](Ollama unavailable — fell back to keyword search)[/dim]\n")

    if json_output:
        console.print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if not results:
        console.print("[dim]No related context found[/dim]")
        return

    console.print(f"[bold]Related context for:[/bold] {query}\n")
    table = Table(title=f"Suggestions ({len(results)})")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white", no_wrap=False)
    table.add_column("Type", style="magenta")
    table.add_column("Project", style="dim")

    for r in results:
        value_short = r["value"][:50] + "..." if len(r["value"]) > 50 else r["value"]
        proj_name = r.get("project_id") or "-"
        table.add_row(r["key"], value_short, r["type"], proj_name)

    console.print(table)


# ─── CONFIG ────────────────────────────────────────────────────────────────────

config_app = typer.Typer(name="config", help="Manage NeuralClaw configuration")
app.add_typer(config_app)


@config_app.command(name="show")
def config_show():
    """Show current NeuralClaw configuration."""
    from neuralclaw.config import load_config
    config = load_config()
    import yaml
    console.print(f"[bold]NeuralClaw config:[/bold] {config.config_path}")
    console.print(yaml.dump(config._data, default_flow_style=False))


@config_app.command(name="set")
def config_set(
    key: str = typer.Argument(..., help="Config key (dot notation, e.g. search.method)"),
    value: str = typer.Argument(..., help="Value to set"),
):
    """Set a configuration value.

    Examples:
      neuralclaw config set search.method embeddings
      neuralclaw config set ollama.base_url http://localhost:11434
      neuralclaw config set ollama.enabled true
      neuralclaw config set search.embeddings_model nomic-embed-text
    """
    from neuralclaw.config import load_config
    config = load_config()

    # Parse dot notation
    parts = key.split(".")
    if len(parts) == 1:
        config.set(key, value)
    else:
        section = parts[0]
        subkey = parts[1]
        if section not in config._data:
            config._data[section] = {}
        # Convert string booleans
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        config._data[section][subkey] = value

    config.save()
    console.print(f"[green]✓[/green] Set [bold]{key}[/bold] = {value!r}")


@config_app.command(name="init")
def config_init():
    """Initialize the config file with defaults (if not exists)."""
    from neuralclaw.config import ensure_config
    config = ensure_config()
    console.print(f"[green]✓[/green] Config initialized at {config.config_path}")


@config_app.command(name="ollama-status")
def config_ollama_status():
    """Check Ollama status and list available models."""
    from neuralclaw.core.embeddings import OllamaEmbeddings

    client = OllamaEmbeddings()
    if client.is_available():
        console.print("[green]✓[/green] Ollama is running")
        console.print(f"  Base URL: {client.base_url}")
        models = client.list_models()
        console.print(f"  Models available: {len(models)}")
        for m in models:
            marker = "[yellow]*[/yellow]" if m == client.model else "  "
            console.print(f"  {marker} {m}")
    else:
        console.print("[red]✗[/red] Ollama is not running")
        console.print(f"  Expected at: {client.base_url}")
        console.print("  Start Ollama with: ollama serve")


@app.command()
def embeddings(
    text: Optional[str] = typer.Argument(None, help="Text to embed (or prompt for interactive mode)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    pull: bool = typer.Option(False, "--pull", help="Pull the model if not available"),
):
    """Compute embedding for text using Ollama.

    If no text provided, enters interactive mode.
    Use --pull to automatically pull the model if not available.
    """
    from neuralclaw.core.embeddings import OllamaEmbeddings

    client = OllamaEmbeddings()
    if not client.is_available():
        console.print("[red]✗[/red] Ollama is not running at {client.base_url}")
        console.print("  Start with: ollama serve")
        raise typer.Exit(1)

    if model:
        client.model = model

    if not client.model_exists():
        if pull:
            console.print(f"[cyan]Pulling model {client.model}...[/cyan]")
            if client.pull_model():
                console.print(f"[green]✓[/green] Model {client.model} pulled")
            else:
                console.print(f"[red]✗[/red] Failed to pull model {client.model}")
                raise typer.Exit(1)
        else:
            console.print(f"[red]Model {client.model} not available[/red]")
            console.print(f"  Available: {', '.join(client.list_models())}")
            console.print("  Use --pull to download it automatically")
            raise typer.Exit(1)

    if text:
        emb = client.embed(text)
        if emb:
            console.print(f"[green]✓[/green] Embedding computed ({len(emb)} dimensions)")
            console.print(f"[dim]First 5 values: {emb[:5]}[/dim]")
        else:
            console.print("[red]✗[/red] Failed to compute embedding")
    else:
        console.print("[dim]Interactive mode - enter text to embed (Ctrl+C to exit)[/dim]")
        while True:
            try:
                line = Prompt.ask("text")
                if not line.strip():
                    continue
                emb = client.embed(line)
                if emb:
                    console.print(f"  ✓ ({len(emb)}d) [dim]{emb[:5]}[/dim]")
                else:
                    console.print("  ✗ Failed")
            except KeyboardInterrupt:
                break


# ─── MAIN ──────────────────────────────────────────────────────────────────────

@app.callback()
def callback():
    """NeuralClaw - Local Context OS for AI Agents."""
    pass


if __name__ == "__main__":
    app()
