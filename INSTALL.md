# NeuralClaw Installation Guide / Guía de Instalación

**English** | [Español](#español)

---

## English Version

### Prerequisites

- **Python 3.11+** installed
- **pip** or **pipx** for package management
- (Optional) **Git** for clone install

### Installation Methods

#### Method 1: Git Clone (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/maxsarlijagit/neuralclaw.git
cd neuralclaw

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install with all features
pip install -e ".[full]"

# Verify installation
neuralclaw --version
```

#### Method 2: pipx (Recommended for Global Install)

```bash
git clone https://github.com/maxsarlijagit/neuralclaw.git
cd neuralclaw
pipx install .
```

#### Method 3: pip

```bash
pip install neuralclaw
```

---

### First Run Setup

After installation, run the interactive setup wizard:

```bash
neuralclaw init
```

The wizard guides you through 4 steps:

```
┌─────────────────────────────────────────────────────────┐
│           🤖 NeuralClaw First Run Setup                 │
├─────────────────────────────────────────────────────────┤
│  Step 1: System Initialization                         │
│           → Creates config, database, vault            │
│                                                         │
│  Step 2: Auto-Setup Projects                            │
│           → Scans for projects, creates 'default'     │
│                                                         │
│  Step 3: AI Adapter Selection                          │
│           → OpenClaw, Claude, ChatGPT                  │
│                                                         │
│  Step 4: Ollama Integration (Optional)                 │
│           → Enable semantic search                      │
│                                                         │
│                    ✅ Setup Complete!                   │
└─────────────────────────────────────────────────────────┘
```

For non-interactive/automated setup:

```bash
neuralclaw init -y
```

---

### Quick Start Commands

```bash
# Add context items
neuralclaw add "DATABASE_URL=postgres://localhost/mydb" --type variable --tags prod,database

# Search
neuralclaw search "database"
neuralclaw search --project default --type variable --limit 20 --offset 0

# Export context for AI agents
neuralclaw context --project default --adapter openclaw

# Backup your data
neuralclaw backup -o backup.json

# Run health checks
neuralclaw doctor

# See all commands
neuralclaw --help
```

---

### Full Command Reference

```
init           Initialize NeuralClaw (interactive wizard)
add            Add a context item (key=value format)
search         Search context items (supports --limit and --offset)
context        Export context as JSON for an AI agent
project        Manage projects (create, list, archive, delete, status)
vault          Manage encrypted secrets (set, get, list, delete)
backup         Export all data as JSON
restore        Restore from backup file
delete         Delete context item by ID (with confirmation)
import-cmd     Bulk import from JSON/JSONL files
doctor         Run health checks
fresh          Generate FreshApple snapshots
tui            Launch interactive Text User Interface
serve          Start FastAPI REST API server (requires -e ".[api]")
version        Show NeuralClaw version
```

---

### Troubleshooting

**"neuralclaw: command not found"**
```bash
# Make sure your venv is activated
source venv/bin/activate

# Or check Python path
which neuralclaw
pip show neuralclaw
```

**"Module not found: fastapi"** when running `neuralclaw serve`
```bash
pip install -e ".[api]"  # Install API dependencies
```

**Database locked or corrupted**
```bash
neuralclaw backup -o emergency_backup.json
# Delete ~/.config/neuralclaw/neuralclaw.db
neuralclaw init
neuralclaw restore emergency_backup.json
```

---

## Español

### Requisitos Previos

- **Python 3.11+** instalado
- **pip** o **pipx** para gestión de paquetes
- (Opcional) **Git** para instalación por clone

### Métodos de Instalación

#### Método 1: Git Clone (Recomendado para Desarrollo)

```bash
# Clonar el repositorio
git clone https://github.com/maxsarlijagit/neuralclaw.git
cd neuralclaw

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar con todas las features
pip install -e ".[full]"

# Verificar instalación
neuralclaw --version
```

#### Método 2: pipx (Recomendado para Instalación Global)

```bash
git clone https://github.com/maxsarlijagit/neuralclaw.git
cd neuralclaw
pipx install .
```

#### Método 3: pip

```bash
pip install neuralclaw
```

---

### Primera Configuración

Después de instalar, ejecutá el wizard interactivo:

```bash
neuralclaw init
```

El wizard te guía por 4 pasos:

```
┌─────────────────────────────────────────────────────────┐
│           🤖 NeuralClaw First Run Setup                 │
├─────────────────────────────────────────────────────────┤
│  Step 1: System Initialization                         │
│           → Crea config, base de datos, vault          │
│                                                         │
│  Step 2: Auto-Setup Projects                           │
│           → Escanea proyectos, crea 'default'          │
│                                                         │
│  Step 3: AI Adapter Selection                          │
│           → OpenClaw, Claude, ChatGPT                  │
│                                                         │
│  Step 4: Ollama Integration (Optional)                 │
│           → Habilita búsqueda semántica                │
│                                                         │
│                    ✅ Setup Complete!                   │
└─────────────────────────────────────────────────────────┘
```

Para configuración no-interactiva:

```bash
neuralclaw init -y
```

---

### Comandos Básicos

```bash
# Agregar items de contexto
neuralclaw add "DATABASE_URL=postgres://localhost/mydb" --type variable --tags prod,database

# Buscar
neuralclaw search "database"
neuralclaw search --project default --type variable --limit 20 --offset 0

# Exportar contexto para agentes IA
neuralclaw context --project default --adapter openclaw

# Backup de tus datos
neuralclaw backup -o backup.json

# Verificar salud del sistema
neuralclaw doctor

# Ver todos los comandos
neuralclaw --help
```

---

### Referencia Completa de Comandos

```
init           Inicializar NeuralClaw (wizard interactivo)
add            Agregar item de contexto (formato key=value)
search         Buscar items (soporta --limit y --offset)
context        Exportar contexto como JSON para agente IA
project        Gestionar proyectos (create, list, archive, delete, status)
vault          Gestionar secrets cifrados (set, get, list, delete)
backup         Exportar todos los datos como JSON
restore        Restaurar desde archivo de backup
delete         Eliminar item por ID (con confirmación)
import-cmd     Importación masiva desde JSON/JSONL
doctor         Ejecutar checks de salud
fresh          Generar snapshots FreshApple
tui            Lanzar interfaz de texto interactiva
serve          Iniciar servidor REST API (requiere -e ".[api]")
version        Mostrar versión de NeuralClaw
```

---

### Solución de Problemas

**"neuralclaw: command not found"**
```bash
# Asegurate de tener el venv activado
source venv/bin/activate

# O verificá el path de Python
which neuralclaw
pip show neuralclaw
```

**"Module not found: fastapi"** al ejecutar `neuralclaw serve`
```bash
pip install -e ".[api]"  # Instalar dependencias de API
```

**Base de datos bloqueada o corrupta**
```bash
neuralclaw backup -o backup_emergencia.json
# Eliminar ~/.config/neuralclaw/neuralclaw.db
neuralclaw init
neuralclaw restore backup_emergencia.json
```

---

*For more info: https://github.com/maxsarlijagit/neuralclaw*