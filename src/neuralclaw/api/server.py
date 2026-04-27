"""FastAPI REST API server for NeuralClaw."""

import json
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from neuralclaw.db.connection import db_exists
from neuralclaw.core.projects import (
    create_project, list_projects, get_project,
    project_exists
)
from neuralclaw.core.context import (
    search_context, get_context_item, add_context_item,
    update_context_item_state, count_context_items
)
from neuralclaw.core.vault import (
    vault_set, vault_get, vault_list, vault_delete, vault_exists
)
from neuralclaw.core.bridge import export_context_json


app = FastAPI(
    title="NeuralClaw API",
    description="Local Context OS for AI Agents - REST API",
    version="0.5.0",
)

# ─── HEALTH ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.5.0",
        "db_exists": db_exists(),
        "vault_exists": vault_exists(),
        "timestamp": datetime.now().isoformat(),
    }


# ─── PROJECTS ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/projects")
def get_projects(status: Optional[str] = Query(None, description="Filter by status: active, archived")):
    """List all projects."""
    projects = list_projects(status=status)
    return {"projects": projects, "count": len(projects)}


@app.post("/api/v1/projects")
def create_project_endpoint(name: str, description: str = ""):
    """Create a new project."""
    try:
        project_id = create_project(name, description)
        project = get_project(project_id)
        return {"project": project, "created": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/projects/{project_id}")
def get_project_endpoint(project_id: str):
    """Get a project by ID or name."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return {"project": project}


@app.get("/api/v1/projects/{project_id}/context")
def get_project_context(
    project_id: str,
    query: Optional[str] = Query(None, description="Search query"),
    state: Optional[str] = Query(None, description="Filter by state"),
    item_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=500),
):
    """Get context items for a project."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    results = search_context(
        query=query,
        project_id=project["id"],
        state=state,
        item_type=item_type,
        limit=limit,
    )
    return {"items": results, "count": len(results), "project": project["name"]}


# ─── CONTEXT ITEMS ────────────────────────────────────────────────────────────

@app.post("/api/v1/context/items")
def create_context_item(
    project_id: Optional[str] = None,
    key: str = Query(..., description="Context item key"),
    value: str = Query(..., description="Context item value"),
    item_type: str = Query("note", description="Item type: note, decision, error, variable, preference"),
    state: str = Query("active", description="State: active, stale, verified, deprecated, archived, conflicting"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    confidence: float = Query(1.0, ge=0.0, le=1.0),
):
    """Create a new context item."""
    if project_id and not project_exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    project_obj = get_project(project_id) if project_id else None
    actual_project_id = project_obj["id"] if project_obj else None

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    item_id = add_context_item(
        project_id=actual_project_id,
        key=key,
        value=value,
        item_type=item_type,
        state=state,
        tags=tag_list,
        confidence=confidence,
    )
    return {"id": item_id, "created": True}


@app.get("/api/v1/context/items")
def list_context_items(
    project_id: Optional[str] = Query(None, description="Filter by project"),
    query: Optional[str] = Query(None, description="Search query"),
    state: Optional[str] = Query(None, description="Filter by state"),
    item_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=500),
):
    """List context items with filters."""
    proj = get_project(project_id) if project_id else None
    actual_project_id = proj["id"] if proj else None

    results = search_context(
        query=query,
        project_id=actual_project_id,
        state=state,
        item_type=item_type,
        limit=limit,
    )
    return {"items": results, "count": len(results)}


@app.get("/api/v1/context/items/{item_id}")
def get_context_item_endpoint(item_id: str):
    """Get a single context item by ID."""
    item = get_context_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Context item '{item_id}' not found")
    return {"item": item}


@app.put("/api/v1/context/items/{item_id}/state")
def update_item_state(item_id: str, state: str = Query(..., description="New state")):
    """Update the state of a context item."""
    item = get_context_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Context item '{item_id}' not found")

    success = update_context_item_state(item_id, state)
    return {"success": success, "new_state": state}


@app.post("/api/v1/context/export")
def export_context(
    task: str = Query("", description="Task description"),
    project_id: Optional[str] = Query(None, description="Project ID or name"),
    adapter: str = Query("openclaw", description="Adapter: openclaw, chatgpt, claude"),
    include_vars: bool = Query(False, description="Include vault variable values"),
    query: Optional[str] = Query(None, description="Search query to filter context"),
):
    """Export context as JSON for an AI adapter."""
    proj = get_project(project_id) if project_id else None
    actual_project_id = proj["id"] if proj else None

    try:
        json_str = export_context_json(
            task=task,
            project_id=actual_project_id,
            adapter_name=adapter,
            include_vars=include_vars,
            query=query,
        )
        data = json.loads(json_str)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── VAULT ─────────────────────────────────────────────────────────────────────

@app.get("/api/v1/vault")
def get_vault():
    """List all vault secrets (names only, no values)."""
    if not vault_exists():
        return {"secrets": [], "count": 0, "initialized": False}
    secrets = vault_list()
    return {"secrets": secrets, "count": len(secrets), "initialized": True}


@app.post("/api/v1/vault")
def set_vault_secret(name: str = Query(..., description="Secret name"), value: str = Query(..., description="Secret value")):
    """Store a secret in the vault."""
    vault_set(name.upper(), value)
    return {"name": name.upper(), "stored": True}


@app.get("/api/v1/vault/{name}")
def get_vault_secret(name: str, reveal: bool = Query(False, description="Show the actual value")):
    """Retrieve a secret from the vault."""
    val = vault_get(name.upper())
    if val is None:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
    if reveal:
        return {"name": name.upper(), "value": val}
    return {"name": name.upper(), "value_set": True}


@app.delete("/api/v1/vault/{name}")
def delete_vault_secret(name: str):
    """Delete a secret from the vault."""
    deleted = vault_delete(name.upper())
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
    return {"name": name.upper(), "deleted": True}


# ─── DOCTOR ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/doctor")
def doctor_check():
    """Run health check on all NeuralClaw systems."""
    issues = []
    warnings = []

    if not db_exists():
        issues.append({"component": "database", "severity": "error", "message": "Database not initialized"})
    else:
        total = count_context_items()
        if total == 0:
            warnings.append({"component": "context", "severity": "warning", "message": "No context items yet"})

    if not vault_exists():
        warnings.append({"component": "vault", "severity": "warning", "message": "Vault not initialized (run neuralclaw init)"})
    else:
        secrets = vault_list()
        if len(secrets) == 0:
            warnings.append({"component": "vault", "severity": "warning", "message": "No secrets stored"})

    status = "healthy"
    if issues:
        status = "unhealthy"
    elif warnings:
        status = "warning"

    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "db_exists": db_exists(),
            "vault_exists": vault_exists(),
            "vault_secret_count": len(vault_list()) if vault_exists() else 0,
        }
    }


# ─── WEB DASHBOARD ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Simple HTML dashboard."""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>NeuralClaw Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f1a; color: #e0e0e0; padding: 2rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #00d4ff; margin-bottom: 0.5rem; font-size: 2rem; }
        .subtitle { color: #888; margin-bottom: 2rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; }
        .card { background: #1a1a2e; border-radius: 12px; padding: 1.5rem; border: 1px solid #2a2a4a; }
        .card h2 { color: #00d4ff; font-size: 1rem; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 1px; }
        .status-item { display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #2a2a4a; }
        .status-item:last-child { border-bottom: none; }
        .status-ok { color: #00ff88; }
        .status-warn { color: #ffaa00; }
        .status-error { color: #ff4444; }
        .api-section { margin-top: 2rem; }
        .endpoint { background: #0a0a15; padding: 0.75rem 1rem; border-radius: 8px; margin: 0.5rem 0; font-family: monospace; font-size: 0.85rem; color: #aaa; }
        .method { color: #00d4ff; font-weight: bold; }
        .method.post { color: #00ff88; }
        .method.delete { color: #ff6b6b; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem; }
        .badge.green { background: #00ff8833; color: #00ff88; }
        .badge.blue { background: #00d4ff33; color: #00d4ff; }
        .badge.yellow { background: #ffaa0033; color: #ffaa00; }
        a { color: #00d4ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .footer { margin-top: 3rem; text-align: center; color: #555; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ NeuralClaw</h1>
        <p class="subtitle">Local Context OS for AI Agents</p>

        <div class="grid">
            <div class="card">
                <h2>System Status</h2>
                <div id="health">
                    <div class="status-item"><span>Loading...</span></div>
                </div>
            </div>
            <div class="card">
                <h2>Quick Actions</h2>
                <div class="status-item"><a href="/api/v1/projects">GET /api/v1/projects</a> <span class="badge green">GET</span></div>
                <div class="status-item"><a href="/api/v1/vault">GET /api/v1/vault</a> <span class="badge green">GET</span></div>
                <div class="status-item"><a href="/api/v1/doctor">GET /api/v1/doctor</a> <span class="badge blue">health</span></div>
                <div class="status-item"><a href="/docs">GET /docs</a> <span class="badge blue">Swagger UI</span></div>
            </div>
            <div class="card">
                <h2>Endpoints</h2>
                <div class="endpoint"><span class="method">GET</span> /api/v1/health</div>
                <div class="endpoint"><span class="method">GET</span> /api/v1/projects</div>
                <div class="endpoint"><span class="method post">POST</span> /api/v1/projects?name=...</div>
                <div class="endpoint"><span class="method">GET</span> /api/v1/context/items</div>
                <div class="endpoint"><span class="method post">POST</span> /api/v1/context/items</div>
                <div class="endpoint"><span class="method">GET</span> /api/v1/vault</div>
                <div class="endpoint"><span class="method post">POST</span> /api/v1/vault?name=...&value=...</div>
            </div>
        </div>

        <div class="footer">
            NeuralClaw v0.5.0 | <a href="/docs">API Documentation</a>
        </div>
    </div>

    <script>
    async function loadHealth() {
        try {
            const res = await fetch('/api/v1/health');
            const data = await res.json();
            document.getElementById('health').innerHTML = `
                <div class="status-item">
                    <span>Database</span>
                    <span class="${data.db_exists ? 'status-ok' : 'status-error'}">${data.db_exists ? '✓ OK' : '✗ Missing'}</span>
                </div>
                <div class="status-item">
                    <span>Vault</span>
                    <span class="${data.vault_exists ? 'status-ok' : 'status-warn'}">${data.vault_exists ? '✓ OK' : '⚠ Not initialized'}</span>
                </div>
                <div class="status-item">
                    <span>Version</span>
                    <span>${data.version}</span>
                </div>
            `;
        } catch(e) {
            document.getElementById('health').innerHTML = '<div class="status-item"><span class="status-error">Failed to load status</span></div>';
        }
    }
    loadHealth();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html)


# ─── RUN SERVER ────────────────────────────────────────────────────────────────

def run_server(host: str = "0.0.0.0", port: int = 7890):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()