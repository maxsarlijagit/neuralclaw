"""NeuralClaw CLI - Single-file main with all commands."""

import json
import time
import sys
import typer
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.style import Style

from neuralclaw.db.connection import (
    init_db, db_exists, get_config_dir, get_schema_version
)
from neuralclaw.core.vault import (
    vault_set, vault_get, vault_list, vault_delete, vault_exists, init_vault
)
from neuralclaw.core.context import (
    add_context_item, get_context_item, get_all_items,
    delete_context_item, count_context_items
)
from neuralclaw.core.search import search_context_smart, search_context_keyword
from neuralclaw.core.projects import (
    create_project, list_projects, get_project,
    archive_project, delete_project, project_exists
)
from neuralclaw.core.bridge import export_context_json
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
    is_fresh
)
from neuralclaw.core.doctor import run_doctor_checks, print_doctor_report
from neuralclaw.logging import log_command


# ═══════════════════════════════════════════════════════════════════════════════
# EXAMPLES — Real-world usage examples for help and tutorials
# ═══════════════════════════════════════════════════════════════════════════════

EXAMPLES = """
[bold cyan]═══ NeuralClaw Quick Examples ═══[/bold cyan]

[bold yellow]Adding context:[/bold yellow]
  neuralclaw add "DATABASE_URL=postgres://localhost/mydb" --project mi-app
  neuralclaw add "decision: use Redis for session cache" --tags architecture
  neuralclaw add "Error: timeout on /api/auth" --type error --tags prod,auth
  neuralclaw add "deploy: run migrate.sh before shipping" --type process
  neuralclaw add "User prefers dark mode" --type preference --project mi-app

[bold yellow]Smart shortcuts (auto-detect type):[/bold yellow]
  neuralclaw add "API_KEY=sk_abc123"           → type: variable (auto-detected)
  neuralclaw add "decision: use Postgres"      → type: decision (auto-detected)
  neuralclaw add "BUG: crash on login"         → type: error (auto-detected)
  neuralclaw add "TODO: refactor auth module"  → type: note (default)

[bold yellow]Searching:[/bold yellow]
  neuralclaw search database
  neuralclaw search "error" --type error --project mi-app
  neuralclaw search --interactive             → Interactive search mode
  neuralclaw suggest "how do I handle auth"    → Semantic search

[bold yellow]Projects:[/bold yellow]
  neuralclaw project create "mi-proyecto" --description "Mi primer proyecto"
  neuralclaw project list
  neuralclaw project status mi-proyecto
  neuralclaw project archive mi-proyecto

[bold yellow]Vault (encrypted secrets):[/bold yellow]
  neuralclaw vault set OPENAI_API_KEY sk-...
  neuralclaw vault list
  neuralclaw vault get OPENAI_API_KEY --reveal

[bold yellow]Context for AI agents:[/bold yellow]
  neuralclaw context --project mi-app --task "implement login"
  neuralclaw context --project mi-app --adapter claude --include-vars
  neuralclaw fresh --project mi-app            → Markdown snapshot

[bold yellow]Backup & Restore:[/bold yellow]
  neuralclaw backup --output backup.json
  neuralclaw restore backup.json
  neuralclaw import --from bulk.json --project mi-app

[bold yellow]Health check:[/bold yellow]
  neuralclaw doctor                           → Full system diagnostic
  neuralclaw status                          → Quick status overview
"""


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBALS — Verbose/quiet state
# ═══════════════════════════════════════════════════════════════════════════════

VERBOSE = False
QUIET = False

def _log_verbose(msg: str):
    """Print message only in verbose mode."""
    if VERBOSE:
        console.print(f"[dim]→ {msg}[/dim]")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════

app = typer.Typer(
    name="neuralclaw",
    help="NeuralClaw — Local Context OS for AI Agents",
    add_completion=False,
    invoke_without_command=True,
)

__version__ = "0.4.1"

# Sub-groups
project_app = typer.Typer(name="project", help="Manage projects")
vault_app = typer.Typer(name="vault", help="Manage encrypted secrets")
plugin_app = typer.Typer(name="plugin", help="Manage plugins")
train_room_app = typer.Typer(name="train-room", help="Train Room — analyze samples and generate profiles")
playroom_app = typer.Typer(name="playroom", help="Playroom — test adapters side-by-side")
cc_app = typer.Typer(name="cc", help="Claude Code — use NeuralClaw as active, token-optimized memory")

app.add_typer(project_app)
app.add_typer(vault_app)
app.add_typer(plugin_app)
app.add_typer(train_room_app)
app.add_typer(playroom_app)
app.add_typer(cc_app)

console = Console()


# ═══════════════════════════════════════════════════════════════════════════════
# TYPE INFERENCE — Smart detection of context item type from content
# ═══════════════════════════════════════════════════════════════════════════════

def _infer_type_from_content(item: str) -> tuple[str, list[str], str]:
    """
    Infer item type, suggested tags, and key from content.
    Returns: (type, suggested_tags, key_hint)
    
    Type detection rules:
    - KEY=value or KEY: value → type: variable
    - "decision:" prefix → type: decision
    - "Error:", "BUG:", "FIX:", "CRASH:" → type: error
    - "TODO:", "NOTE:", "FIXME:" → type: note
    - "deploy:", "run:", "execute:" → type: process
    - "preference:", "user prefers:", "likes:" → type: preference
    - "industry:", "market:", "competitor:" → type: industry
    - Default → type: note
    """
    item_lower = item.lower().strip()
    tags = []
    
    # Variable detection: KEY=value or KEY: value at start
    if "=" in item and item.index("=") < 50:
        key_candidate = item.split("=", 1)[0].strip()
        if key_candidate and " " not in key_candidate and not any(
            k in item_lower for k in ["decision:", "error:", "todo:", "note:", "deploy:", "bug:"]
        ):
            return "variable", [], key_candidate
    
    # Decision
    if item_lower.startswith("decision:"):
        return "decision", ["decision"], "decision"
    
    # Error patterns
    error_prefixes = ["error:", "bug:", "crash:", "fix:", "failed:", "failure:"]
    for prefix in error_prefixes:
        if item_lower.startswith(prefix):
            # Extract error code/name for tag
            after_prefix = item.split(":", 1)[1].strip()[:30] if ":" in item else ""
            tags = ["error", prefix.rstrip(":").replace(":", "")]
            return "error", tags, f"error-{after_prefix[:20].replace(' ', '-')}" if after_prefix else "error"
    
    # Process patterns
    if item_lower.startswith(("deploy:", "run:", "execute:", "build:", "test:")):
        return "process", ["process"], item_lower.split(":")[0].replace(":", "")
    
    # Preference patterns
    if item_lower.startswith(("preference:", "user prefers:", "likes:", "dislikes:")):
        return "preference", ["preference"], "preference"
    
    # Note patterns
    note_prefixes = ["todo:", "note:", "fixme:", "hack:", "reminder:"]
    for prefix in note_prefixes:
        if item_lower.startswith(prefix):
            return "note", ["note"], prefix.rstrip(":")
    
    # Industry patterns
    if item_lower.startswith(("industry:", "market:", "competitor:", "trend:")):
        return "industry", ["industry"], "industry"
    
    # Default
    return "note", [], "note"


# ═══════════════════════════════════════════════════════════════════════════════
# SUGGEST SIMILAR — Did you mean functionality
# ═══════════════════════════════════════════════════════════════════════════════

def _suggest_similar(query: str, items: list, key_field: str = "name", limit: int = 3) -> list:
    """Simple suggest similar items based on string similarity."""
    if not query or not items:
        return []
    
    query_lower = query.lower()
    scored = []
    
    for item in items:
        item_val = str(item.get(key_field, "")).lower()
        # Simple scoring: count matching chars in sequence
        score = 0
        q_idx = 0
        for c in item_val:
            if q_idx < len(query_lower) and c == query_lower[q_idx]:
                score += 1
                q_idx += 1
        # Also check if query is substring
        if query_lower in item_val:
            score += len(query_lower) * 2
        # Check Levenshtein-like: common prefix
        common_prefix = 0
        for i, c in enumerate(query_lower):
            if i < len(item_val) and item_val[i] == c:
                common_prefix += 1
            else:
                break
        score += common_prefix * 2
        
        if score > 0:
            scored.append((score, item))
    
    scored.sort(reverse=True, key=lambda x: x[0])
    return [item for _, item in scored[:limit]]


def _print_suggestion_hint(query: str, project_name: str = None):
    """Print hint when something is not found."""
    # Try to suggest similar projects
    if project_name:
        projects = list_projects(status=None)
        similar = _suggest_similar(project_name, projects, key_field="name")
        if similar:
            console.print()
            console.print("[dim]¿Quisiste decir?[/dim]")
            for p in similar:
                console.print(f"  [cyan]→[/cyan] {p['name']} ({p['status']})")


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO SETUP
# ═══════════════════════════════════════════════════════════════════════════════

def _auto_setup():
    """Auto-create default project if DB exists but has no projects."""
    if not db_exists():
        return
    if not vault_exists():
        return
    try:
        from neuralclaw.core.projects import list_projects
        projects = list_projects()
        if len(projects) == 0:
            from neuralclaw.core.projects import create_project
            create_project("default", "Default project created automatically")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CALLBACK — Global flags (verbose, quiet)
# ═══════════════════════════════════════════════════════════════════════════════

@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Quiet mode (minimal output)"),
):
    """NeuralClaw — Local Context OS for AI Agents."""
    global VERBOSE, QUIET
    VERBOSE = verbose
    QUIET = quiet
    
    if version:
        console.print(f"[cyan]NeuralClaw[/cyan] [bold]{__version__}[/bold]")
        raise typer.Exit()


# ═══════════════════════════════════════════════════════════════════════════════
# VERSION COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

@app.command(name="version")
def version():
    """Show NeuralClaw version."""
    console.print(f"[cyan]NeuralClaw[/cyan] version [bold]{__version__}[/bold]")


# ═══════════════════════════════════════════════════════════════════════════════
# EXAMPLES COMMAND — Show usage examples
# ═══════════════════════════════════════════════════════════════════════════════

@app.command(name="examples")
def examples():
    """Show real-world usage examples."""
    console.print(Panel.fit(
        EXAMPLES,
        title="NeuralClaw Examples",
        border_style="cyan",
        padding=1,
    ))


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
        console.print("[green]Starting NeuralClaw API server...[/green]")
        console.print(f"  Dashboard: http://localhost:{port}/")
        console.print(f"  API docs:  http://localhost:{port}/docs")
        run_server(host=host, port=port)
    except ImportError:
        console.print("[red]Error:[/red] FastAPI and uvicorn required. Install with: pip install fastapi uvicorn")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# INSTALL COMPLETION COMMAND — Shell completion
# ═══════════════════════════════════════════════════════════════════════════════

@app.command(name="install-completion")
def install_completion(
    shell: str = typer.Argument("bash", help="Shell type: bash, zsh, fish"),
):
    """Install shell completion for NeuralClaw.
    
    Examples:
      neuralclaw install-completion bash
      neuralclaw install-completion zsh
      neuralclaw install-completion fish
    """
    if shell == "bash":
        completion_script = f"""
# NeuralClaw shell completion - Add to ~/.bashrc
eval "$(_NEURALCLAW_COMPLETE=bash_source neuralclaw)"
"""
        rc_file = Path.home() / ".bashrc"
        console.print(f"[cyan]→[/cyan] Add to your [bold]{rc_file}[/bold]:")
        console.print(completion_script)
        
    elif shell == "zsh":
        completion_script = f"""
# NeuralClaw shell completion - Add to ~/.zshrc
autoload -U compinit
compinit
eval "$(_NEURALCLAW_COMPLETE=zsh_source neuralclaw)"
"""
        rc_file = Path.home() / ".zshrc"
        console.print(f"[cyan]→[/cyan] Add to your [bold]{rc_file}[/bold]:")
        console.print(completion_script)
        
    elif shell == "fish":
        console.print(f"[cyan]→[/cyan] Run this command:")
        console.print(f"  neuralclaw --completion fish | source")
        console.print()
        console.print("Or add to your [bold]~/.config/fish/config.fish[/bold]:")
        console.print("  neuralclaw --completion fish | source")
    else:
        console.print(f"[red]Error:[/red] Unsupported shell: {shell}")
        console.print("  Supported: bash, zsh, fish")
        raise typer.Exit(1)
    
    console.print()
    console.print("[dim]After adding, restart your shell or run: source ~/.bashrc (or ~/.zshrc)[/dim]")


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS COMMAND — Quick dashboard
# ═══════════════════════════════════════════════════════════════════════════════

@app.command(name="status")
def status():
    """Show a quick status overview of NeuralClaw.
    
    Displays: projects, context items, vault status, and health summary.
    """
    from neuralclaw.db.connection import get_config_dir
    
    if not db_exists():
        console.print(Panel.fit(
            "[yellow]NeuralClaw not initialized[/yellow]\n\nRun [cyan]neuralclaw init[/cyan] to set up.",
            title="NeuralClaw Status",
            border_style="yellow",
        ))
        return
    
    # Projects
    all_projects = list_projects(status=None)
    active_projects = [p for p in all_projects if p["status"] == "active"]
    archived_projects = [p for p in all_projects if p["status"] == "archived"]
    
    # Context items
    total_items = count_context_items()
    active_items = count_context_items(state="active")
    stale_items = count_context_items(state="stale")
    
    # Vault
    vault_count = len(vault_list()) if vault_exists() else 0
    
    # Schema version
    schema_ver = get_schema_version()
    config_dir = get_config_dir()
    
    # Build status table
    status_table = Table(box=None, padding=(0, 2))
    status_table.add_column("[bold]Component[/bold]", style="cyan")
    status_table.add_column("[bold]Status[/bold]", style="green")
    
    status_table.add_row("Version", f"v{__version__}")
    status_table.add_row("Schema", f"v{schema_ver}")
    status_table.add_row("Projects", f"{len(active_projects)} active, {len(archived_projects)} archived")
    status_table.add_row("Context Items", f"{total_items} total ({active_items} active, {stale_items} stale)")
    status_table.add_row("Vault", f"{vault_count} secrets stored" if vault_exists() else "[yellow]not initialized[/yellow]")
    status_table.add_row("Config", str(config_dir))
    
    console.print(Panel.fit(
        status_table,
        title=f"[bold]NeuralClaw Status[/bold] — v{__version__}",
        border_style="cyan",
        padding=1,
    ))
    
    # Quick health
    console.print()
    if stale_items > 0:
        console.print(f"[yellow]⚠ {stale_items} stale items. Run 'neuralclaw doctor' for details.[/yellow]")
    else:
        console.print("[green]✓ All systems healthy[/green]")
    
    # Next steps hint
    if total_items == 0 and len(active_projects) <= 1:
        console.print()
        console.print("[dim]💡 Tip: Run 'neuralclaw examples' to see usage examples.[/dim]")


# ═══════════════════════════════════════════════════════════════════════════════
# TUTORIAL COMMAND — Interactive walkthrough
# ═══════════════════════════════════════════════════════════════════════════════

@app.command(name="tutorial")
def tutorial():
    """Launch an interactive walkthrough to learn NeuralClaw.
    
    Guides you through the core features step by step.
    """
    from neuralclaw.core.projects import create_project
    
    steps = [
        {
            "title": "🚀 Welcome to NeuralClaw",
            "content": """NeuralClaw is your **local context OS for AI agents**.

It helps you organize:
• Project decisions and architecture choices
• Secrets and API keys (encrypted)
• Errors and how you solved them
• Variables and configuration
• Communication preferences for AI agents

[dim]Let's get started![/dim]""",
            "action": None,
        },
        {
            "title": "📝 Step 1: Add your first context item",
            "content": """Context items are the building blocks of NeuralClaw.

[bold]Try these commands:[/bold]

[cyan]neuralclaw add "MY_PROJECT=awesome-app"[/cyan]
  → Saves a variable

[cyan]neuralclaw add "decision: use PostgreSQL for main DB"[/cyan]
  → Saves an architectural decision

[cyan]neuralclaw add "Error: memory leak in worker process"[/cyan]
  → Logs an error for future reference

[dim]All items are stored locally and encrypted (secrets).[/dim]""",
            "action": None,
        },
        {
            "title": "🔍 Step 2: Search your context",
            "content": """Find anything you've saved:

[cyan]neuralclaw search database[/cyan]
  → Search by keyword

[cyan]neuralclaw suggest "authentication"[/cyan]
  → Semantic search (requires Ollama)

[cyan]neuralclaw search --interactive[/cyan]
  → Interactive search mode

[dim]Pro tip: Use --type and --tags to filter results.[/dim]""",
            "action": None,
        },
        {
            "title": "🔐 Step 3: Store secrets safely",
            "content": """The vault stores secrets encrypted:

[cyan]neuralclaw vault set OPENAI_KEY sk-...[/cyan]
  → Store a secret

[cyan]neuralclaw vault list[/cyan]
  → See all secrets (names only)

[cyan]neuralclaw vault get OPENAI_KEY --reveal[/cyan]
  → Reveal a secret

[dim]Values are encrypted with Fernet (AES-128-CBC).[/dim]""",
            "action": None,
        },
        {
            "title": "🤖 Step 4: Export context for AI agents",
            "content": """NeuralClaw formats context for different AI systems:

[cyan]neuralclaw context --project mi-app --task "implement login"[/cyan]
  → Export context as JSON

[cyan]neuralclaw context --adapter claude --project mi-app[/cyan]
  → Format for Claude specifically

[cyan]neuralclaw fresh --project mi-app[/cyan]
  → Get a markdown snapshot

[dim]Adapters ensure each AI gets context in its preferred format.[/dim]""",
            "action": None,
        },
        {
            "title": "🏥 Step 5: Health check",
            "content": """Keep your system healthy:

[cyan]neuralclaw doctor[/cyan]
  → Full diagnostic (DB, vault, stale items, conflicts)

[cyan]neuralclaw status[/cyan]
  → Quick overview

[dim]Run doctor periodically to clean up stale items.[/dim]""",
            "action": None,
        },
        {
            "title": "✅ You're ready!",
            "content": """[bold green]NeuralClaw is now yours.[/bold green]

[bold]Quick reference:[/bold]
  neuralclaw add           → Add context
  neuralclaw search        → Find context
  neuralclaw vault         → Manage secrets
  neuralclaw context       → Export for AI
  neuralclaw doctor        → Health check
  neuralclaw examples     → See more examples

[dim]Type 'neuralclaw --help' for all commands.[/dim]""",
            "action": None,
        },
    ]
    
    current_step = 0
    
    while True:
        step = steps[current_step]
        
        console.print(Panel.fit(
            step["content"],
            title=step["title"],
            border_style="cyan",
            padding=1,
        ))
        
        # Navigation
        console.print()
        nav_options = []
        if current_step > 0:
            nav_options.append("[b]←[/b] Previous")
        if current_step < len(steps) - 1:
            nav_options.append("[b]→[/b] Next")
        nav_options.append("[b]q[/b] Quit tutorial")
        
        console.print("  ".join(nav_options))
        console.print()
        
        choice = Prompt.ask(
            "[cyan]Choose[/cyan]",
            default="n" if current_step < len(steps) - 1 else "q"
        )
        
        if choice.lower() in ("q", "quit", "exit"):
            console.print("\n[dim]Tutorial exited. Happy context managing![/dim]\n")
            break
        elif choice.lower() in ("p", "prev", "←", "back") and current_step > 0:
            current_step -= 1
        elif choice.lower() in ("n", "next", "→", "enter") and current_step < len(steps) - 1:
            current_step += 1
        else:
            if current_step == len(steps) - 1:
                break


# ═══════════════════════════════════════════════════════════════════════════════
# INIT COMMAND — With onboarding checklist
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def init(
    non_interactive: bool = typer.Option(False, "--yes", "-y", help="Skip interactive prompts (for automation)")
):
    """Initialize NeuralClaw with an interactive setup wizard.
    
    Creates config directory, database, vault, and optionally
    guides you through creating your first project and selecting adapters.
    """
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
    # WELCOME
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
    # STEP 1: System Initialization
    # ═══════════════════════════════════════════════════════════════════════
    console.print(Panel.fit(
        "[bold]Step 1: System Initialization[/bold]",
        border_style="green"
    ))
    
    config_dir = get_config_dir()
    console.print(f"\n[dim]Config directory:[/dim] [cyan]{config_dir}[/cyan]")
    
    if not db_exists():
        init_db()
        console.print("[green]✓[/green] Database created")
    else:
        version = get_schema_version()
        console.print(f"[yellow]✓[/yellow] Database exists (v{version})")
    
    if not vault_exists():
        init_vault()
        console.print("[green]✓[/green] Vault initialized (secrets encrypted)")
    else:
        console.print("[yellow]✓[/yellow] Vault already exists")
    
    console.print()
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: Auto-Setup Projects
    # ═══════════════════════════════════════════════════════════════════════
    console.print(Panel.fit(
        "[bold]Step 2: Auto-Setup Projects[/bold]",
        border_style="green"
    ))
    console.print("[dim]Checking for existing projects...[/dim]\n")
    
    existing_projects = []
    try:
        existing_projects = list_projects()  # noqa: F823 - imported at module level
    except Exception:
        pass
    
    if len(existing_projects) == 0:
        console.print("[cyan]→[/cyan] No projects found. Creating 'default' project automatically...")
        try:
            create_project("default", "Default project created automatically on first setup")
            console.print("[green]✓[/green] Project 'default' created")
        except Exception as e:
            console.print(f"[yellow]![/yellow] Could not auto-create project: {e}")
    else:
        project_names = [p["name"] for p in existing_projects]
        console.print(f"[green]✓[/green] Found {len(existing_projects)} project(s): [cyan]{', '.join(project_names)}[/cyan]")
    
    console.print()
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: AI Adapters
    # ═══════════════════════════════════════════════════════════════════════
    console.print(Panel.fit(
        "[bold]Step 3: AI Adapters[/bold]",
        border_style="green"
    ))
    console.print("[dim]Select the AI systems you work with:[/dim]\n")
    
    if non_interactive:
        enabled_adapters = ["openclaw", "claude", "chatgpt"]
    else:
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
    # STEP 4: Ollama (optional)
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
    # COMPLETION — WITH ONBOARDING CHECKLIST
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
        "[dim]Database:[/dim]    SQLite (local)",
        "[dim]Vault:[/dim]       Encrypted with Fernet",
        f"[dim]Projects:[/dim]   {len(projects)} created",
        f"[dim]Adapters:[/dim]    {', '.join(enabled_adapters)}",
    ]
    
    for line in summary_lines:
        console.print(f"  {line}")
    
    console.print()
    
    # ═══════════════════════════════════════════════════════════════════════
    # ONBOARDING CHECKLIST
    # ═══════════════════════════════════════════════════════════════════════
    console.print(Panel.fit(
        "[bold]📋 Your Next Steps[/bold]\n\n"
        "[cyan]1.[/cyan] Add your first context item:\n"
        "      neuralclaw add [yellow]\"MY_KEY=my_value\"[/yellow]\n\n"
        "[cyan]2.[/cyan] Try smart shortcuts (auto-detect type):\n"
        "      neuralclaw add [yellow]\"decision: use Postgres for DB\"[/yellow]\n\n"
        "[cyan]3.[/cyan] Search what you saved:\n"
        "      neuralclaw search [yellow]keyword[/yellow]\n\n"
        "[cyan]4.[/cyan] Export context for an AI agent:\n"
        "      neuralclaw context --project default --task [yellow]\"my task\"[/yellow]\n\n"
        "[cyan]5.[/cyan] Run a health check:\n"
        "      neuralclaw doctor\n\n"
        "[cyan]6.[/cyan] See more examples:\n"
        "      neuralclaw examples\n\n"
        "[dim]Or run the interactive tutorial: neuralclaw tutorial[/dim]",
        title="🚀 Onboarding Checklist",
        border_style="cyan",
        padding=1,
    ))
    
    console.print()
    
    if not non_interactive:
        run_tutorial = Confirm.ask(
            "[cyan]¿Querés ejecutar el tutorial interactivo?[/cyan]",
            default=True
        )
        if run_tutorial:
            console.print()
            tutorial()


# ═══════════════════════════════════════════════════════════════════════════════
# ADD COMMAND — With smart inference
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def add(
    item: str = typer.Argument(..., help="Context item. Formats: 'key=value', 'key:value', or free text"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name or ID"),
    item_type: str = typer.Option(None, "--type", "-t", help="Type: note, decision, error, variable, preference, process, industry"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
    stale_after: Optional[int] = typer.Option(None, "--stale-after", help="Unix timestamp after which item is stale"),
    confidence: float = typer.Option(1.0, "--confidence", help="Confidence 0.0-1.0"),
    state: str = typer.Option("active", "--state", "-s", help="State: active, stale, verified, deprecated, archived, conflicting"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode with prompts"),
):
    """Add a context item.
    
    Smart inference: type is auto-detected from content when not specified.
    
    Examples:
      neuralclaw add "DATABASE_URL=postgres://localhost/mydb"
      neuralclaw add "decision: use Redis for cache" --tags architecture
      neuralclaw add "Error: timeout on /api/auth" --type error
      neuralclaw add "deploy: run migrate.sh before shipping" --type process
    """
    # Parse key/value
    if "=" in item:
        key, value = item.split("=", 1)
    elif ":" in item:
        key, value = item.split(":", 1)
    else:
        key, value = item, ""
    
    key, value = key.strip(), value.strip()
    
    # Smart type inference
    if item_type is None:
        inferred_type, inferred_tags, _ = _infer_type_from_content(item)
        if inferred_type != "note" or inferred_tags:
            console.print(f"[dim]💡 Auto-detected type: {inferred_type}[/dim]")
            if inferred_tags and not tags:
                tags = ",".join(inferred_tags)
                console.print(f"[dim]   Suggested tags: {tags}[/dim]")
        item_type = inferred_type
    
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    
    # Interactive mode
    if interactive or (not key and not value):
        console.print("[cyan]Interactive mode - Add context item[/cyan]")
        if not key:
            key = Prompt.ask("Key (e.g. DATABASE_URL)")
        if not value:
            value = Prompt.ask("Value")
        if item_type is None or item_type == "note":
            type_options = ["note", "decision", "error", "variable", "preference", "process", "industry"]
            item_type = Prompt.ask("Type", choices=type_options, default="note")
        if not tags:
            tags = Prompt.ask("Tags (comma-separated, optional)", default="")
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    if not key:
        console.print("[red]Error:[/red] Key cannot be empty")
        raise typer.Exit(1)
    
    # Project validation with suggestion
    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            _print_suggestion_hint(project)
            raise typer.Exit(1)
        project_id = get_project(project)["id"]
    
    item_id = add_context_item(
        project_id=project_id, key=key, value=value,
        item_type=item_type, state=state, tags=tag_list,
        stale_after=stale_after, confidence=confidence,
    )
    
    if not QUIET:
        console.print(f"[green]✓[/green] Added [bold]{key}[/bold]")
        if not VERBOSE:
            console.print(f"  ID: {item_id}")
            console.print(f"  Type: {item_type} | State: {state}")
            if project:
                console.print(f"  Project: {project}")
            if tag_list:
                console.print(f"  Tags: {', '.join(tag_list)}")
    
    # Smart tip
    if item_type == "note" and not tags:
        console.print("[dim]💡 Tip: For decisions use 'decision:' prefix, for errors use 'Error:'[/dim]")


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH COMMAND — With interactive mode
# ═══════════════════════════════════════════════════════════════════════════════

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
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive search mode"),
):
    """Search context items.
    
    Examples:
      neuralclaw search database
      neuralclaw search "error" --type error --project mi-app
      neuralclaw search --interactive
      neuralclaw search --type decision --limit 20
    """
    # Interactive mode
    if interactive:
        _run_interactive_search()
        return
    
    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            _print_suggestion_hint(project)
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

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

    results = run_context_search_hooks(query=query or None, project_id=project_id, results=results)

    if json_output:
        console.print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if not results:
        if offset > 0:
            console.print(f"[dim]No more results (page offset: {offset})[/dim]")
        else:
            console.print("[dim]No results found[/dim]")
            if query:
                console.print(f"[dim]💡 Try 'neuralclaw suggest \"{query}\"' for semantic search[/dim]")
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


def _run_interactive_search():
    """Interactive search mode with filters and pagination."""
    from rich.prompt import Prompt
    from rich.console import Console as RichConsole
    
    console.print(Panel.fit(
        "[bold cyan]🔍 Interactive Search[/bold cyan]\n\n"
        "[dim]Search your context items interactively[/dim]\n"
        "[dim]Press Ctrl+C to exit[/dim]",
        border_style="cyan",
    ))
    console.print()
    
    # Current filters
    filters = {
        "query": "",
        "project": None,
        "type": None,
        "state": None,
        "tags": None,
        "limit": 20,
        "offset": 0,
    }
    
    while True:
        # Build display
        console.print(f"\n[bold]Query:[/bold] {filters['query'] or '[dim](empty)[/dim]'}")
        if filters["project"]:
            console.print(f"[bold]Project:[/bold] {filters['project']}")
        if filters["type"]:
            console.print(f"[bold]Type:[/bold] {filters['type']}")
        if filters["state"]:
            console.print(f"[bold]State:[/bold] {filters['state']}")
        console.print(f"[bold]Limit:[/bold] {filters['limit']} | [bold]Offset:[/bold] {filters['offset']}")
        console.print()
        
        # Execute search
        project_id = None
        if filters["project"]:
            proj = get_project(filters["project"])
            if proj:
                project_id = proj["id"]
        
        tag_list = filters["tags"].split(",") if filters["tags"] else None
        
        results = search_context_smart(
            query=filters["query"] or None,
            project_id=project_id,
            state=filters["state"],
            item_type=filters["type"],
            tags=tag_list,
            limit=filters["limit"],
            offset=filters["offset"],
            method="auto",
        )
        
        if not results:
            console.print("[dim]No results found[/dim]")
        else:
            console.print(f"[dim]Found {len(results)} results[/dim]\n")
            table = Table(box=None)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white", no_wrap=False)
            table.add_column("Type", style="magenta")
            table.add_column("State", style="green")
            
            for r in results:
                value_short = r["value"][:40] + "..." if len(r["value"]) > 40 else r["value"]
                table.add_row(r["key"], value_short, r["type"], r["state"])
            console.print(table)
        
        console.print()
        console.print("[cyan]Commands:[/cyan] [bold]q[/bold] quit  [bold]query[/bold] <text>  [bold]proj[/bold] <name>  [bold]type[/bold] <type>  [bold]state[/bold] <state>  [bold]tags[/bold] <tags>  [bold]+[/bold] [bold]-[/bold]")
        
        try:
            cmd = Prompt.ask("\n[cyan]>[/cyan] ", default="")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Search exited.[/dim]\n")
            break
        
        cmd = cmd.strip()
        if not cmd:
            continue
        
        parts = cmd.split(None, 1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        if action == "q":
            break
        elif action == "query":
            filters["query"] = arg
            filters["offset"] = 0
        elif action == "proj":
            filters["project"] = arg if arg else None
            filters["offset"] = 0
        elif action == "type":
            filters["type"] = arg if arg else None
            filters["offset"] = 0
        elif action == "state":
            filters["state"] = arg if arg else None
            filters["offset"] = 0
        elif action == "tags":
            filters["tags"] = arg if arg else None
            filters["offset"] = 0
        elif action == "+":
            filters["offset"] += filters["limit"]
        elif action == "-":
            filters["offset"] = max(0, filters["offset"] - filters["limit"])
        elif action == "clear":
            filters = {"query": "", "project": None, "type": None, "state": None, "tags": None, "limit": 20, "offset": 0}


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

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
            _print_suggestion_hint(project)
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    try:
        json_str = export_context_json(
            task=task, project_id=project_id,
            adapter_name=adapter, include_vars=include_vars, query=query,
        )
        if json_output:
            import json as _json
            export_data = _json.loads(json_str)
            export_data = run_context_export_hooks(export_data)
            json_str = _json.dumps(export_data, indent=2, ensure_ascii=False)
        console.print(json_str)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT SUB-GROUP
# ═══════════════════════════════════════════════════════════════════════════════

@project_app.command(name="create")
def project_create(
    name: str = typer.Argument(..., help="Project name"),
    description: str = typer.Option("", "--description", "-d", help="Project description"),
):
    """Create a new project.
    
    Examples:
      neuralclaw project create "mi-proyecto" --description "Mi primer proyecto"
      neuralclaw project create backend --description "API backend service"
    """
    try:
        project_id = create_project(name, description)
        console.print(f"[green]✓[/green] Project [bold]{name}[/bold] created")
        if VERBOSE:
            console.print(f"  ID: {project_id}")
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            console.print(f"[red]Error:[/red] Project '{name}' already exists.")
            _print_suggestion_hint(name)
        else:
            raise


@project_app.command(name="list")
def project_list(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter: active, archived"),
):
    """List all projects.
    
    Examples:
      neuralclaw project list
      neuralclaw project list --status archived
    """
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
    """Archive a project.
    
    Examples:
      neuralclaw project archive mi-proyecto
    """
    project = get_project(name)
    if not project:
        console.print(f"[red]Error:[/red] Project '{name}' not found.")
        _print_suggestion_hint(name)
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
    """Delete a project and all its context items.
    
    Examples:
      neuralclaw project delete mi-proyecto
      neuralclaw project delete mi-proyecto --force
    """
    project = get_project(name)
    if not project:
        console.print(f"[red]Error:[/red] Project '{name}' not found.")
        _print_suggestion_hint(name)
        raise typer.Exit(1)
    if not force and not Confirm.ask(f"Delete project [bold]{project['name']}[/bold] and ALL its context items?"):
        console.print("[yellow]Cancelled[/yellow]")
        return
    delete_project(project["id"])
    console.print(f"[green]✓[/green] Project [bold]{project['name']}[/bold] deleted")


@project_app.command(name="status")
def project_status(name: str = typer.Argument(..., help="Project name or ID")):
    """Show project status.
    
    Examples:
      neuralclaw project status mi-proyecto
    """
    project = get_project(name)
    if not project:
        console.print(f"[red]Error:[/red] Project '{name}' not found.")
        _print_suggestion_hint(name)
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


# ═══════════════════════════════════════════════════════════════════════════════
# VAULT SUB-GROUP
# ═══════════════════════════════════════════════════════════════════════════════

@vault_app.command(name="set")
def vault_set_cmd(
    name: str = typer.Argument(..., help="Secret name (e.g. OPENAI_API_KEY)"),
    value: Optional[str] = typer.Argument(None, help="Secret value (will prompt if not provided)"),
):
    """Store a secret in the vault.
    
    Examples:
      neuralclaw vault set OPENAI_API_KEY sk-...
      echo "my-secret" | neuralclaw vault set MY_KEY
    """
    if not value:
        value = Prompt.ask(f"Enter value for [bold]{name}[/bold]", password=True)
    vault_set(name.upper(), value)
    console.print(f"[green]✓[/green] Secret [bold]{name.upper()}[/bold] stored")


@vault_app.command(name="get")
def vault_get_cmd(
    name: str = typer.Argument(..., help="Secret name"),
    reveal: bool = typer.Option(False, "--reveal", help="Show the actual value"),
):
    """Retrieve a secret from the vault.
    
    Examples:
      neuralclaw vault get OPENAI_API_KEY
      neuralclaw vault get OPENAI_API_KEY --reveal
    """
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
    """List all secrets (names only).
    
    Examples:
      neuralclaw vault list
    """
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
    """Delete a secret from the vault.
    
    Examples:
      neuralclaw vault delete OPENAI_API_KEY
      neuralclaw vault delete OPENAI_API_KEY --force
    """
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
    """Show vault status.
    
    Examples:
      neuralclaw vault status
    """
    if not vault_exists():
        console.print("[yellow]Vault not initialized (run 'neuralclaw init')[/yellow]")
        return
    secrets = vault_list()
    console.print("[green]✓[/green] Vault initialized")
    console.print(f"  Secrets stored: {len(secrets)}")


# ═══════════════════════════════════════════════════════════════════════════════
# FRESH COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

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

    Examples:
      neuralclaw fresh --project mi-app
      neuralclaw fresh --project mi-app --regenerate
      neuralclaw fresh --project mi-app --ttl 7200
    """
    project_id = None
    project_name = None

    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            _print_suggestion_hint(project)
            raise typer.Exit(1)
        proj = get_project(project)
        project_id = proj["id"]
        project_name = proj["name"]

    # Check cache unless regenerating
    if not regenerate and project_id:
        if is_fresh(project_id, ttl_seconds=ttl):
            fa = get_fresh_apple(project_id)
            if fa:
                if not QUIET:
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
        if saved_id and not QUIET:
            console.print(f"[green]✓[/green] FreshApple saved to DB (ID: {saved_id[:8]}...)")
        elif not saved_id:
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


# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def import_cmd(
    from_file: str = typer.Option(..., "--from", "-f", help="Input file (JSON or JSONL)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Default project for items"),
    batch_size: int = typer.Option(100, "--batch-size", help="Batch size for bulk insert"),
):
    """Bulk import context items from a JSON or JSONL file.
    
    Examples:
      neuralclaw import --from backup.json
      neuralclaw import --from items.jsonl --project mi-app
      cat data.json | neuralclaw import --from -
    """
    from neuralclaw.logging import log_info

    # Handle stdin
    if from_file == "-":
        content = sys.stdin.read()
    else:
        input_path = Path(from_file)
        if not input_path.exists():
            console.print(f"[red]Error:[/red] File not found: {input_path}")
            raise typer.Exit(1)
        try:
            content = input_path.read_text(encoding="utf-8").strip()
        except Exception as e:
            console.print(f"[red]Error:[/red] Could not read file: {e}")
            raise typer.Exit(1)

    # Detect format: JSONL if lines, JSON if array
    items = []
    if content.startswith("["):
        try:
            items = json.loads(content)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error:[/red] Invalid JSON: {e}")
            raise typer.Exit(1)
    else:
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

    if not QUIET:
        console.print(f"[cyan]Importing {len(items)} items...[/cyan]")

    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            _print_suggestion_hint(project)
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

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


# ═══════════════════════════════════════════════════════════════════════════════
# BACKUP & RESTORE
# ═══════════════════════════════════════════════════════════════════════════════

@app.command(name="backup")
def backup_cmd(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (.json or .json.gz)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Backup specific project"),
    pretty: bool = typer.Option(True, "--pretty/--no-pretty", help="Human-readable JSON"),
):
    """Export all context items, projects, and vault entries as JSON backup.
    
    Examples:
      neuralclaw backup
      neuralclaw backup --output backup.json
      neuralclaw backup --project mi-app --output mi-app_backup.json.gz
    """
    import gzip
    from pathlib import Path
    
    projects = list_projects()
    
    project_id = None
    if project:
        proj = get_project(project)
        if not proj:
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            _print_suggestion_hint(project)
            raise typer.Exit(1)
        project_id = proj["id"]
    
    context_items = get_all_items(project_id=project_id)
    
    vault_entries = []
    if vault_exists():
        vault_entries = vault_list()
    
    backup = {
        "version": "0.4.1",
        "exported_at": datetime.now().isoformat(),
        "projects": projects,
        "context_items": context_items,
        "vault_metadata": vault_entries,
        "schema_version": get_schema_version(),
    }
    
    if not output:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "_" + project if project else ""
        output = f"neuralclaw_backup_{ts}{suffix}.json"
    
    output_path = Path(output).expanduser()
    
    if str(output).endswith(".gz"):
        with gzip.open(output_path, "wt", encoding="utf-8") as f:
            json.dump(backup, f, indent=2 if pretty else None)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(backup, f, indent=2 if pretty else None)
    
    if not QUIET:
        console.print(f"[green]✓[/green] Backup saved to [bold]{output_path}[/bold]")
        console.print(f"  Projects: {len(projects)}")
        console.print(f"  Context items: {len(context_items)}")
        console.print(f"  Vault entries: {len(vault_entries)}")
        console.print("\n[dim]Note: Vault values are NOT exported (security).[/dim]")


@app.command(name="restore")
def restore_cmd(
    from_file: str = typer.Argument(..., help="Backup file to restore (.json or .json.gz)"),
    merge: bool = typer.Option(True, "--merge/--replace", help="Merge with existing data or replace"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Restore context items and projects from a backup file.
    
    Examples:
      neuralclaw restore backup_20260427.json
      neuralclaw restore backup.json --replace
    """
    import gzip
    from pathlib import Path
    
    backup_path = Path(from_file).expanduser()
    if not backup_path.exists():
        console.print(f"[red]Error:[/red] Backup file not found: {from_file}")
        raise typer.Exit(1)
    
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
    
    projects_restored = 0
    for proj in backup.get("projects", []):
        if not project_exists(proj["name"]):
            create_project(proj["name"], proj.get("description", ""))
            projects_restored += 1
    
    items_restored = 0
    for item in backup["context_items"]:
        try:
            proj_id = item.get("project_id")
            if proj_id:
                proj = get_project(proj_id)
                if not proj:
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
    
    console.print("[green]✓[/green] Restore complete")
    console.print(f"  Projects created: {projects_restored}")
    console.print(f"  Context items restored: {items_restored}")


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE CONTEXT ITEM
# ═══════════════════════════════════════════════════════════════════════════════

@app.command(name="delete")
def delete_item_cmd(
    item_id: str = typer.Argument(..., help="Context item ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a context item by ID.
    
    Examples:
      neuralclaw delete item_id_123
      neuralclaw search database  # find the ID first
    """
    item = get_context_item(item_id)
    if not item:
        console.print(f"[red]Error:[/red] Item not found: {item_id}")
        raise typer.Exit(1)
    
    console.print("[cyan]Item details:[/cyan]")
    console.print(f"  Key: [bold]{item['key']}[/bold]")
    console.print(f"  Value: {item.get('value', '')[:60]}...")
    console.print(f"  Type: {item.get('type', 'note')} | State: {item.get('state', 'active')}")
    if item.get('project_id'):
        console.print(f"  Project: {item['project_id']}")
    
    if not force and not Confirm.ask("\nDelete this item?"):
        console.print("[yellow]Cancelled[/yellow]")
        return
    
    success = delete_context_item(item_id)
    if success:
        console.print("[green]✓[/green] Item deleted")
    else:
        console.print("[red]Error:[/red] Could not delete item")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def doctor():
    """Run health checks on the NeuralClaw system.

    Examples:
      neuralclaw doctor
    """
    results, pass_count, total = run_doctor_checks()
    print_doctor_report(results, pass_count, total)


# ═══════════════════════════════════════════════════════════════════════════════
# PLUGIN SUB-GROUP
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# TRAIN ROOM SUB-GROUP
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# PLAYROOM SUB-GROUP
# ═══════════════════════════════════════════════════════════════════════════════

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
            _print_suggestion_hint(project)
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    console.print(f"[cyan]Testing prompt across:[/cyan] {', '.join(adapter_names)}\n")
    try:
        result = test_prompt(prompt, adapter_names, project_id=project_id)
        print_comparison(result)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# SUGGEST COMMAND — Semantic search
# ═══════════════════════════════════════════════════════════════════════════════

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

    Examples:
      neuralclaw suggest "authentication flow"
      neuralclaw suggest "database connection issues"
    """
    project_id = None
    if project:
        if not project_exists(project):
            console.print(f"[red]Error:[/red] Project '{project}' not found.")
            _print_suggestion_hint(project)
            raise typer.Exit(1)
        project_id = get_project(project)["id"]

    from neuralclaw.core.context import suggest_context as _suggest_context
    results = _suggest_context(query=query, project_id=project_id, limit=limit)

    if not results:
        # Fall back to keyword search
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


# ═══════════════════════════════════════════════════════════════════════════════
# CC SUB-GROUP — Claude Code active memory
# ═══════════════════════════════════════════════════════════════════════════════

@cc_app.command(name="recall")
def cc_recall(
    query: str = typer.Argument("", help="What you're working on (focuses recall)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name or ID"),
    token_budget: int = typer.Option(2000, "--budget", "-b", help="Max tokens for the memory block"),
    method: str = typer.Option("keyword", "--method", "-m", help="keyword | fts | embeddings"),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of markdown"),
):
    """Recall token-budgeted, relevance-ranked memory for the current task."""
    from neuralclaw.integrations.claude_code import memory as _mem
    result = _mem.recall(
        query=query or None, project=project,
        token_budget=token_budget, method=method,
    )
    if json_output:
        console.print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        console.print(_mem.render_markdown(result))


@cc_app.command(name="remember")
def cc_remember(
    content: str = typer.Argument(..., help="The fact/decision/error to remember"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name or ID"),
    item_type: Optional[str] = typer.Option(None, "--type", "-t", help="Override auto-detected type"),
    key: Optional[str] = typer.Option(None, "--key", "-k", help="Stable key (default: inferred)"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
):
    """Store a fact into persistent memory (same store the MCP tool writes to)."""
    from neuralclaw.integrations.claude_code import memory as _mem
    project_id = _mem.resolve_project_id(project)
    inferred_type, inferred_tags, inferred_key = _infer_type_from_content(content)
    resolved_type = item_type or inferred_type
    if key:
        resolved_key = key
    elif inferred_key and inferred_key != "note":
        resolved_key = inferred_key
    else:
        resolved_key = content[:40].strip()
    tag_list = [t.strip() for t in tags.split(",")] if tags else (inferred_tags or None)
    item_id = add_context_item(
        project_id=project_id, key=resolved_key, value=content,
        item_type=resolved_type, tags=tag_list,
    )
    console.print(f"[green]✓[/green] Stored [bold]{resolved_type}[/bold] `{resolved_key}` "
                  f"(project={project or 'global'})")
    _log_verbose(f"id={item_id}")


@cc_app.command(name="snapshot")
def cc_snapshot(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name or ID"),
):
    """Print a FreshApple markdown snapshot of active context."""
    from neuralclaw.integrations.claude_code import memory as _mem
    project_id = _mem.resolve_project_id(project)
    console.print(generate_fresh_apple(project_id=project_id, project_name=project))


@cc_app.command(name="install")
def cc_install(
    path: str = typer.Option(".", "--path", help="Project root to scaffold"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Default project to scope memory to"),
    token_budget: int = typer.Option(1500, "--budget", "-b", help="SessionStart hook token budget"),
    no_hook: bool = typer.Option(False, "--no-hook", help="Skip the SessionStart hook"),
    no_mcp: bool = typer.Option(False, "--no-mcp", help="Skip the .mcp.json server"),
    no_claude_md: bool = typer.Option(False, "--no-claude-md", help="Skip the CLAUDE.md note"),
):
    """Wire NeuralClaw into a Claude Code project (.mcp.json + hook + CLAUDE.md)."""
    from neuralclaw.integrations.claude_code import scaffold
    from pathlib import Path as _Path
    results = scaffold.install(
        root=_Path(path), project=project, token_budget=token_budget,
        with_hook=not no_hook, with_mcp=not no_mcp, with_claude_md=not no_claude_md,
    )
    console.print(f"[bold cyan]NeuralClaw → Claude Code[/bold cyan] (root: {_Path(path).resolve()})")
    for target, changed in results.items():
        mark = "[green]written[/green]" if changed else "[dim]already configured[/dim]"
        console.print(f"  {mark}  {target}")
    console.print(
        "\n[dim]Next: ensure the [bold]mcp[/bold] extra is installed "
        "([bold]pip install \"neuralclaw-os[claude-code]\"[/bold]) and "
        "restart Claude Code so it picks up the new server + hook.[/dim]"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG SUB-GROUP
# ═══════════════════════════════════════════════════════════════════════════════

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

    parts = key.split(".")
    if len(parts) == 1:
        config.set(key, value)
    else:
        section = parts[0]
        subkey = parts[1]
        if section not in config._data:
            config._data[section] = {}
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

    Examples:
      neuralclaw embeddings "hello world"
      neuralclaw embeddings --model nomic-embed-text --pull
    """
    from neuralclaw.core.embeddings import OllamaEmbeddings

    client = OllamaEmbeddings()
    if not client.is_available():
        console.print(f"[red]✗[/red] Ollama is not running at {client.base_url}")
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


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

@app.callback()
def callback():
    """NeuralClaw - Local Context OS for AI Agents."""
    pass


if __name__ == "__main__":
    app()
