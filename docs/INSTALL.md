# Installation

## Requirements

- Python 3.11 or higher
- pip or pipx

## Install from PyPI

```bash
pip install neuralclaw
```

Then initialize:

```bash
neuralclaw init
```

## Install from Source

```bash
git clone https://github.com/yourusername/neuralclaw.git
cd neuralclaw
pip install -e ".[dev]"
neuralclaw init
```

## Development Installation

```bash
pip install -e ".[dev]"
```

This installs:
- `pytest` — for running tests
- `pytest-cov` — for coverage reports
- `ruff` — for linting

## Verify Installation

```bash
neuralclaw --version
neuralclaw init
```

## Configuration

NeuralClaw stores all data in:

| OS | Path |
|----|------|
| Linux | `~/.config/neuralclaw/` |
| macOS | `~/Library/Application Support/neuralclaw/` |
| Windows | `%APPDATA%\neuralclaw\` |

## Uninstall

```bash
pip uninstall neuralclaw
# Remove config (optional):
rm -rf ~/.config/neuralclaw/
```
