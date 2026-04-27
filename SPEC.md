---

## Decisiones de Diseño — ✅ APROBADAS

| # | Decisión | Valor | Status |
|---|---|---|---|
| 1 | DB global en ~/.config/ | `~/.config/neuralclaw/neuralclaw.db` | ✅ APROBADO |
| 2 | Sync (no async) | `sqlite3` estándar | ✅ APROBADO |
| 3 | Keyword search (no embeddings) | FTS5 de SQLite | ✅ APROBADO |
| 4 | Vault global | Un vault cifrado en config | ✅ APROBADO |
| 5 | FreshApple auto-refresh híbrido | TTL 1h por defecto | ✅ APROBADO |
| 6 | Output solo a stdout | JSON a stdout, archivo opcional | ✅ APROBADO |
| 7 | Python version | 3.11+ | ✅ APROBADO |
| 8 | Packaging | CLI stand-alone (PyPI) | ✅ APROBADO |

---

## Roadmap por Fases

### Fase 1: MVP — Base funcional
**Alcance:**
- `neuralclaw init`
- `neuralclaw add`
- `neuralclaw search`
- `neuralclaw project create`
- `neuralclaw project list`
- `neuralclaw project archive`
- `neuralclaw vault set/list/get`
- `neuralclaw context` (stdout JSON)
- Schema SQL completo
- 3 adapters (openclaw, chatgpt, claude)

**Tiempo estimado:** 3-4 días

---

### Fase 2: Proyectos + Estados + Ranking
**Alcance:**
- Estados completos (8 estados)
- Stale detection con TTL configurable
- Ranking de contexto por relevance score
- Conflict detection
- `neuralclaw doctor` completo
- `neuralclaw fresh`
- FreshApple generation

**Tiempo estimado:** 2-3 días

---

### Fase 3: Integración IA
**Alcance:**
- Plugin system
- Train Room básico
- Playroom para testing
- Context Bridge formateo por adapter
- Más adapters

**Tiempo estimado:** 3-4 días

---

### Fase 4: Embeddings opcionales
**Alcance:**
- FTS5 para keyword search
- Integración Ollama para embeddings
- Búsqueda semántica (opcional, feature flag)

**Tiempo estimado:** 2-3 días

---

### Fase 5: UI
**Alcance:**
- TUI (texto) con Rich
- Opcional: web UI con FastAPI
- Dashboard básico

**Tiempo estimado:** 4-5 días

---

## Scope del MVP (Fase 1) — ✅ APROBADO

**Lo que entra:**
- `neuralclaw init` → genera config + vault.key + DB
- `neuralclaw add` → agrega context items a la DB
- `neuralclaw search` → busca por keyword, filtra por estado/tipo
- `neuralclaw project create/archive/list`
- `neuralclaw vault set/list/get`
- `neuralclaw context` → export JSON formateado para adapter
- Schema SQL completo con todos los módulos
- 3 adapters yaml

**Lo que NO entra en MVP:**
- FreshApple auto-generation
- Doctor
- Playroom
- Train Room
- Plugin system
- Embeddings
- FastAPI server

---

*Implementación iniciada: 2026-04-26*
