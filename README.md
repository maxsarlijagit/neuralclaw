# NeuralClaw

**Local Context OS for AI Agents**

NeuralClaw es un sistema local para organizar memoria, contexto, proyectos, variables, errores, decisiones y preferencias de comunicación, entregando a cada IA/agente solo el contexto mínimo útil.

**No entrena modelos. No reemplaza ChatGPT, Claude ni OpenClaw. Funciona como capa intermedia de contexto.**

---

## Instalación

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

O con pipx:
```bash
pipx install .
```

---

## Inicialización

```bash
neuralclaw init
```

Crea:
- `~/.config/neuralclaw/` — config directory
- `~/.config/neuralclaw/neuralclaw.db` — SQLite database
- `~/.config/neuralclaw/vault.key` — encryption key
- `~/.config/neuralclaw/vault/vault.db` — encrypted secrets

---

## Comandos

### Proyectos

```bash
neuralclaw project create "mi-proyecto" --description "Descripción"
neuralclaw project list
neuralclaw project status "mi-proyecto"
neuralclaw project archive "mi-proyecto"
neuralclaw project delete "mi-proyecto" --force
```

### Context Items

```bash
# Agregar items
neuralclaw add "api_endpoint=https://api.example.com" --project mi-proyecto --type variable --tags api,prod
neuralclaw add "decision: usar Redis para cache" --project mi-proyecto --type decision
neuralclaw add "Error: timeout en /auth" --project mi-proyecto --type error --tags auth,prod

# Buscar
neuralclaw search "api" --project mi-proyecto
neuralclaw search "error" --state stale --type error
```

### Vault (Secrets cifrados)

```bash
neuralclaw vault set OPENAI_API_KEY "sk-..."
neuralclaw vault list
neuralclaw vault get OPENAI_API_KEY --reveal
neuralclaw vault delete OPENAI_API_KEY
```

### Exportar Contexto

```bash
neuralclaw context --project mi-proyecto --task "Implementar auth" --adapter openclaw
```

Output JSON con el contexto formateado para el adapter seleccionado.

---

## Architecture

```
neuralclaw/
├── core/
│   ├── context.py    # CRUD de context items
│   ├── vault.py      # Secrets cifrados (Fernet)
│   ├── projects.py   # Gestión de proyectos
│   └── bridge.py     # Context export JSON
├── db/
│   ├── schema.sql    # Schema SQL completo
│   └── connection.py # DB connection
├── adapters/         # Configs YAML por LLM
│   ├── openclaw.yaml
│   ├── chatgpt.yaml
│   └── claude.yaml
└── cli/
    └── main.py       # CLI completo (single-file)
```

---

## Estados de Contexto

| Estado | Significado |
|---|---|
| `active` | Información vigente |
| `stale` | Puede estar desactualizada |
| `deprecated` | Reemplazada por algo nuevo |
| `archived` | Histórico |
| `conflicting` | Contradice otro item |
| `verified` | Confirmada como correcta |

---

## Adapters

Los adapters definen cómo NeuralClaw formatea el output para cada LLM:

- **openclaw** — formato compacto para OpenClaw
- **chatgpt** — formato para ChatGPT
- **claude** — formato para Claude

---

## Tech Stack

- Python 3.11+
- Typer + Rich (CLI)
- SQLite (local, sin cloud)
- Cryptography (Fernet para vault)

---

## Roadmap

| Fase | Alcance |
|---|---|
| ✅ MVP | init, add, search, project, vault, context |
| Fase 2 | fresh, doctor, stale detection, conflict detection |
| Fase 3 | plugin system, train-room, playroom |
| Fase 4 | embeddings (Ollama), FTS5 |
| Fase 5 | TUI, web UI |

---

*Más info: [SPEC.md](./SPEC.md)*
