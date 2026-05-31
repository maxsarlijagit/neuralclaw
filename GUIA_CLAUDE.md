<div align="center">

# 🧠 NeuralClaw + Claude

**Memoria activa, local y persistente para Claude Code y Claude**

_Tu contexto deja de perderse entre sesiones. Las decisiones, errores y variables
de tu proyecto se recuerdan solos — y siempre dentro de un presupuesto de tokens._

</div>

---

## Índice

1. [¿Qué resuelve esto?](#1-qué-resuelve-esto)
2. [Cómo funciona (en 30 segundos)](#2-cómo-funciona-en-30-segundos)
3. [Requisitos](#3-requisitos)
4. [Instalación](#4-instalación)
5. [Uso en Claude Code](#5-uso-en-claude-code)
6. [Uso en Claude (Desktop y claude.ai)](#6-uso-en-claude-desktop-y-claudeai)
7. [Principios de memoria y optimización de tokens](#7-principios-de-memoria-y-optimización-de-tokens)
8. [Referencia de comandos](#8-referencia-de-comandos)
9. [Configuración](#9-configuración)
10. [Solución de problemas](#10-solución-de-problemas)
11. [Preguntas frecuentes](#11-preguntas-frecuentes)

---

## 1. ¿Qué resuelve esto?

Cuando trabajás con Claude (Code o chat), **el contexto es el verdadero cuello de
botella**: cada sesión nueva empieza en blanco. Re-explicás las decisiones de
arquitectura, los errores que ya resolviste, las variables del entorno…

NeuralClaw guarda todo eso **una sola vez, en tu máquina**, y se lo entrega a
Claude automáticamente — formateado y recortado a un presupuesto de tokens, para
que no malgastes ventana de contexto.

- 🔒 **Local-first.** Nada sale de tu equipo. Sin cuenta, sin nube.
- ♻️ **Persistente entre sesiones.** Lo que aprendiste ayer sigue ahí hoy.
- 🎯 **Optimizado en tokens.** Solo lo relevante, rankeado y con presupuesto.
- 🔌 **Doble integración.** MCP + hooks para Claude Code; MCP + adapter para Claude.

---

## 2. Cómo funciona (en 30 segundos)

```
┌────────────────────┐        ┌──────────────────────────┐
│   Claude Code      │        │   NeuralClaw (local)     │
│   / Claude Desktop │◄──MCP──►│                          │
│                    │  tools │  • SQLite con tu contexto │
│  SessionStart hook │◄───────│  • ranking + presupuesto  │
│  (auto-recall)     │        │  • detección de obsoletos │
└────────────────────┘        └──────────────────────────┘
```

1. **Al iniciar una sesión**, un hook inyecta tu memoria más relevante (auto-recall).
2. **Durante la sesión**, Claude usa herramientas MCP para *leer* (`memory_recall`)
   y *escribir* (`memory_store`) memoria sobre la marcha.
3. **Todo respeta un presupuesto de tokens**: se entrega lo mejor rankeado y se
   reporta lo que quedó fuera.

---

## 3. Requisitos

- **Python 3.11+**
- **Claude Code** (CLI) y/o **Claude Desktop** — ambos soportan MCP
- (Opcional) **Ollama** para búsqueda semántica por embeddings

Comprobá tu Python:

```bash
python --version   # debe ser 3.11 o superior
```

---

## 4. Instalación

### 4.1. Instalá NeuralClaw con el extra de Claude

El extra `[claude-code]` agrega el paquete `mcp` necesario para el servidor.

```bash
pip install "neuralclaw-os[claude-code]"
```

> ¿Instalación desde el repo (desarrollo)?
> ```bash
> git clone https://github.com/maxsarlijagit/neuralclaw
> cd neuralclaw
> pip install -e ".[claude-code]"
> ```

### 4.2. Inicializá NeuralClaw (una vez por máquina)

Crea la base de datos local, el vault cifrado y la config en `~/.config/neuralclaw/`.

```bash
neuralclaw init
```

### 4.3. (Opcional) Creá un proyecto

Para mantener la memoria separada por repositorio:

```bash
neuralclaw project create mi-app --description "Mi aplicación"
```

✅ Listo. Ahora elegí tu camino: [Claude Code](#5-uso-en-claude-code) o
[Claude Desktop/claude.ai](#6-uso-en-claude-desktop-y-claudeai).

---

## 5. Uso en Claude Code

### 5.1. Conectá NeuralClaw a tu proyecto

Desde la raíz de tu repo:

```bash
cd mi-app
neuralclaw cc install --project mi-app
```

Esto escribe **tres archivos** (de forma idempotente y sin pisar lo existente):

| Archivo | Para qué |
|---|---|
| `.mcp.json` | Registra el servidor MCP `neuralclaw-memory` |
| `.claude/settings.json` | Registra el hook `SessionStart` de auto-recall |
| `CLAUDE.md` | Enseña al agente a recordar antes de re-deducir |

Luego **reiniciá Claude Code** para que cargue el servidor y el hook.

> Flags útiles: `--no-hook`, `--no-mcp`, `--no-claude-md`, `--budget 1500`, `--path .`

### 5.2. Qué pasa al abrir una sesión (auto-recall)

Al iniciar Claude Code, el hook inyecta automáticamente un bloque como este,
recortado al presupuesto de tokens:

```markdown
## 🧠 NeuralClaw Memory — mi-app
★ `datastore`: decision: usar Postgres como almacén principal
= `API_RATE_LIMIT`: API_RATE_LIMIT=100 req/min
✗ `error-auth`: BUG: el token expira a los 15min y da 401  ⟨STALE⟩

_~38 tokens · 3/3 items_
```

Claude arranca **ya sabiendo** las decisiones, errores y variables del proyecto.

### 5.3. Herramientas MCP disponibles durante la sesión

Una vez conectado, Claude puede llamar a estas herramientas por su cuenta o si se
lo pedís ("recordá esto", "qué decidimos sobre la base de datos"):

| Herramienta | Qué hace |
|---|---|
| `memory_recall(query, project, token_budget, method)` | Recupera memoria relevante, rankeada y con presupuesto |
| `memory_store(content, item_type, project, tags, confidence)` | Guarda una decisión/error/variable (tipo autodetectado) |
| `memory_get(item_id)` | Expande el valor completo de un item |
| `memory_snapshot(project)` | Snapshot FreshApple del contexto activo |

**Ejemplos de prompts dentro de Claude Code:**

> "Recordá que decidimos cachear las sesiones en Redis."
> → Claude llama `memory_store("decision: cachear sesiones en Redis", project="mi-app")`

> "¿Qué sabemos sobre autenticación en este proyecto?"
> → Claude llama `memory_recall("autenticación", project="mi-app")`

### 5.4. Comandos de terminal equivalentes

Todo lo que hace el agente, lo podés hacer vos:

```bash
# Recuperar memoria para una tarea (markdown con presupuesto de tokens)
neuralclaw cc recall "implementar refresh de tokens" --project mi-app --budget 1500

# Guardar un hecho (tipo autodetectado: decision/error/variable/...)
neuralclaw cc remember "decision: refrescar tokens 60s antes de expirar" -p mi-app

# Snapshot completo del contexto activo
neuralclaw cc snapshot --project mi-app
```

### 5.5. Flujo de trabajo recomendado

```bash
# 1. Inicializás y conectás (una vez por proyecto)
neuralclaw cc install --project mi-app

# 2. Trabajás normalmente en Claude Code.
#    El auto-recall te da contexto al arrancar.

# 3. Cada vez que tomás una decisión o resolvés un bug, lo guardás:
neuralclaw cc remember "decision: migrar a Pydantic v2" -p mi-app
neuralclaw cc remember "BUG: race condition en el worker de colas — resuelto con lock" -p mi-app

# 4. La próxima sesión arranca sabiendo todo eso. Sin copiar y pegar.
```

---

## 6. Uso en Claude (Desktop y claude.ai)

### 6.1. Claude Desktop (vía MCP — recomendado)

Claude Desktop también soporta servidores MCP. Agregá NeuralClaw a su config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "neuralclaw-memory": {
      "command": "neuralclaw-cc-memory",
      "env": { "NEURALCLAW_CC_PROJECT": "mi-app" }
    }
  }
}
```

Reiniciá Claude Desktop. Ahora, en cualquier conversación, Claude puede usar
`memory_recall` y `memory_store` igual que en Claude Code.

> Si `neuralclaw-cc-memory` no está en el PATH del sistema, usá la ruta absoluta
> (por ejemplo la que devuelve `which neuralclaw-cc-memory`).

### 6.2. claude.ai (copiar y pegar — sin MCP)

En la web no hay MCP, pero podés exportar tu contexto formateado para Claude y
pegarlo al inicio de la conversación:

```bash
neuralclaw context --project mi-app --adapter claude --task "implementar login"
```

Esto genera un bloque `[CLAUDE CONTEXT] … [/CLAUDE CONTEXT]` listo para pegar.
Para una vista más humana en markdown:

```bash
neuralclaw cc snapshot --project mi-app | pbcopy   # macOS
neuralclaw cc snapshot --project mi-app | xclip     # Linux
```

Pegás el snapshot, y Claude arranca la conversación con todo el contexto.

---

## 7. Principios de memoria y optimización de tokens

NeuralClaw aplica las mismas ideas con las que Claude gestiona su propia ventana:
mantener el set de trabajo **pequeño, relevante y revelado progresivamente**.

| Principio | Cómo se aplica |
|---|---|
| **Ranking por relevancia** | Puntaje = `relevancia × confianza × peso_de_estado × recencia`. Lo mejor sube. |
| **Presupuesto de tokens** | El recall empaqueta items dentro del budget (2000 por defecto) sin desbordar. Lo que se descarta se reporta, no se pierde en silencio. |
| **Decaimiento por recencia** | El puntaje se reduce a la mitad cada ~30 días: lo fresco gana. |
| **Peso por estado** | `verified` > `active` > `conflicting` > `stale` > `deprecated`; `archived` nunca aparece. |
| **Marcado de obsoletos** | Items vencidos (TTL) se degradan y se marcan `STALE`; los conflictos, `CONFLICT`. |
| **Revelación progresiva** | El recall muestra una línea compacta por item; el valor completo se pide bajo demanda con `memory_get`. |

La estimación de tokens usa la misma heurística (`caracteres ÷ 4`) que el resto de
NeuralClaw, así los cálculos son consistentes en todo el sistema.

**¿Qué significa en la práctica?** Si pedís un recall con presupuesto de 30 tokens:

```
## 🧠 NeuralClaw Memory — mi-app
★ `datastore`: decision: usar Postgres como almacén principal
= `API_RATE_LIMIT`: API_RATE_LIMIT=100 req/min

_+2 más omitidos para respetar el presupuesto de 30 tokens —
afiná la consulta o subí el presupuesto._

_~28 tokens · 2/4 items_
```

---

## 8. Referencia de comandos

### Comandos `cc` (Claude Code)

| Comando | Descripción |
|---|---|
| `neuralclaw cc install` | Conecta el repo (.mcp.json + hook + CLAUDE.md) |
| `neuralclaw cc recall "<tarea>"` | Memoria rankeada y con presupuesto para una tarea |
| `neuralclaw cc remember "<hecho>"` | Guarda una decisión/error/variable |
| `neuralclaw cc snapshot` | Snapshot FreshApple del contexto activo |

### Opciones frecuentes

| Opción | Aplica a | Default |
|---|---|---|
| `--project, -p` | todos | global |
| `--budget, -b` | `recall`, `install` | 2000 / 1500 |
| `--method, -m` | `recall` | `keyword` (o `fts`, `embeddings`) |
| `--type, -t` | `remember` | autodetectado |
| `--json` | `recall` | markdown |

### Scripts de consola instalados

| Script | Uso |
|---|---|
| `neuralclaw-cc-memory` | Servidor MCP (lo lanza Claude Code/Desktop) |
| `neuralclaw-cc-hook` | Hook `SessionStart` (lo lanza Claude Code) |

---

## 9. Configuración

Variables de entorno (todas opcionales):

| Variable | Efecto | Default |
|---|---|---|
| `NEURALCLAW_CC_PROJECT` | Limita el recall/MCP a un proyecto | global |
| `NEURALCLAW_CC_TOKEN_BUDGET` | Presupuesto del bloque de `SessionStart` | `1500` |
| `NEURALCLAW_CC_QUERY` | Consulta de enfoque para el auto-recall | ninguna |

Ejemplo de `.claude/settings.json` generado por `cc install`:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "neuralclaw-cc-hook" }] }
    ]
  },
  "env": {
    "NEURALCLAW_CC_PROJECT": "mi-app",
    "NEURALCLAW_CC_TOKEN_BUDGET": "1500"
  }
}
```

---

## 10. Solución de problemas

**El servidor MCP no aparece en Claude Code/Desktop**
- Reiniciá la app después de `cc install` / de editar la config.
- Verificá que el script esté en el PATH: `which neuralclaw-cc-memory`.
- Si falta el paquete `mcp`: `pip install "neuralclaw-os[claude-code]"`.

**El auto-recall no inyecta nada**
- ¿Inicializaste? `neuralclaw init`.
- ¿Hay memoria guardada para ese proyecto? `neuralclaw cc snapshot -p mi-app`.
- El hook es defensivo: si no hay nada relevante, no imprime nada (es esperado).

**"The 'mcp' package is required…"**
- Instalá el extra: `pip install "neuralclaw-os[claude-code]"`.

**Veo items marcados `STALE` o `CONFLICT`**
- `STALE`: pasó su TTL — verificá el dato antes de confiar.
- `CONFLICT`: hay dos valores distintos para la misma clave — resolvelo guardando
  el valor correcto de nuevo.

---

## 11. Preguntas frecuentes

**¿Mis datos salen de mi máquina?**
No. Todo vive en SQLite local (`~/.config/neuralclaw/`). Sin nube, sin cuenta.

**¿Funciona con varios proyectos a la vez?**
Sí. Usá `--project` (o `NEURALCLAW_CC_PROJECT`) para aislar la memoria por repo.
Sin proyecto, trabajás en memoria global.

**¿Necesito Ollama?**
No. Por defecto la búsqueda es por palabras clave. Ollama solo se usa si pedís
`--method embeddings` para búsqueda semántica.

**¿Esto reemplaza a `CLAUDE.md`?**
No, lo complementa. `CLAUDE.md` es contexto estático que vos escribís; NeuralClaw
es memoria dinámica que crece con tu trabajo y se entrega con presupuesto de tokens.

**¿Por qué un presupuesto de tokens y no inyectar todo?**
Porque la ventana de contexto es cara y finita. Inyectar todo degrada la atención
del modelo. NeuralClaw entrega una rebanada filosa y relevante, no el volcado completo.

---

<div align="center">

Hecho con 🧠 sobre [NeuralClaw](README.md) · _Dejá de copiar contexto. Empezá a construir._

</div>
