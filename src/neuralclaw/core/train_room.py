"""Train Room — Analyze conversation samples and generate communication profiles."""

import json
import re
import statistics
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neuralclaw.db.connection import get_connection

PROFILES_DIR = Path(__file__).parent.parent.parent / "train_room" / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AnalysisResult:
    """Result of analyzing sample texts."""

    avg_response_length: float
    avg_line_count: float
    markdown_usage: float  # 0.0-1.0 proportion of markdown-heavy responses
    formal_ratio: float  # 0.0-1.0 formal vs casual
    technical_ratio: float  # 0.0-1.0 technical vs plain
    brief_ratio: float  # 0.0-1.0 brief vs verbose
    code_block_count: int
    emoji_count: int
    question_count: int
    total_samples: int


def _tokenize(text: str) -> list[str]:
    """Simple word tokenizer."""
    return re.findall(r"\b\w+\b", text.lower())


def _analyze_text(text: str) -> dict[str, Any]:
    """Analyze a single text sample."""
    lines = text.split("\n")
    words = _tokenize(text)

    # Markdown indicators
    has_headers = bool(re.search(r"^#{1,6}\s", text, re.MULTILINE))
    has_code_blocks = "```" in text
    has_lists = bool(re.search(r"^[\-\*\+]\s", text, re.MULTILINE))
    has_tables = "|" in text
    markdown_score = sum([has_headers, has_code_blocks, has_lists, has_tables]) / 4.0

    # Formal indicators
    formal_words = {
        "therefore", "furthermore", "however", "consequently",
        "pursuant", "hereby", "whereas", "hence", "thus",
        "indeed", "shall", "must", "shall", "regarding",
    }
    casual_words = {
        "you", "your", "i", "me", "my", "we", "us",
        "got", "gonna", "wanna", "yeah", "okay", "cool",
        "hey", "oh", "wow", "hey",
    }
    formal_count = sum(1 for w in words if w in formal_words)
    casual_count = sum(1 for w in words if w in casual_words)
    formal_ratio = formal_count / max(len(words), 1)
    casual_ratio = casual_count / max(len(words), 1)

    # Technical indicators
    tech_patterns = [
        r"\b\d+\.\d+\.\d+\b",  # version numbers
        r"\b\w+\.\w+\(\)",  # function calls
        r"\b(API|CLI|HTTP|JSON|JSON|YAML|SQL|REST)\b",
        r"```",
        r"<[^>]+>",
        r"\b(AWS|GCP|Azure|K8s|Docker|Postgres|Mongo|Redis)\b",
    ]
    tech_count = sum(len(re.findall(p, text)) for p in tech_patterns)
    technical_ratio = min(tech_count / max(len(words), 1) * 10, 1.0)

    # Length indicators
    word_count = len(words)
    is_brief = word_count < 50
    is_medium = 50 <= word_count <= 200
    is_long = word_count > 200

    # Count special elements
    code_blocks = len(re.findall(r"```[\s\S]*?```", text))
    emojis = len(re.findall(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]", text))
    questions = text.count("?")

    return {
        "word_count": word_count,
        "line_count": len([l for l in lines if l.strip()]),
        "markdown_score": markdown_score,
        "formal_ratio": formal_ratio,
        "technical_ratio": technical_ratio,
        "is_brief": is_brief,
        "is_medium": is_medium,
        "is_long": is_long,
        "code_blocks": code_blocks,
        "emojis": emojis,
        "questions": questions,
    }


def analyze_samples(samples_dir: Path) -> AnalysisResult:
    """Analyze all text files in a samples directory."""
    texts: list[str] = []

    if samples_dir.is_file():
        texts.append(samples_dir.read_text(encoding="utf-8", errors="ignore"))
    else:
        for pattern in ("*.txt", "*.md", "*.json", "*.py"):
            for f in samples_dir.glob(pattern):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    # For JSON files, extract "content" or "text" or "response" fields
                    if f.suffix == ".json":
                        try:
                            data = json.loads(content)
                            if isinstance(data, str):
                                content = data
                            elif isinstance(data, dict):
                                content = data.get("content") or data.get("text") or data.get("response", "")
                        except json.JSONDecodeError:
                            pass
                    texts.append(content)
                except Exception:
                    pass

    if not texts:
        raise ValueError(f"No sample files found in {samples_dir}")

    results = [_analyze_text(t) for t in texts]

    avg_len = statistics.mean(r["word_count"] for r in results) if results else 0
    avg_lines = statistics.mean(r["line_count"] for r in results) if results else 0
    avg_md = statistics.mean(r["markdown_score"] for r in results) if results else 0
    avg_formal = statistics.mean(r["formal_ratio"] for r in results) if results else 0
    avg_tech = statistics.mean(r["technical_ratio"] for r in results) if results else 0
    brief_count = sum(1 for r in results if r["is_brief"])
    medium_count = sum(1 for r in results if r["is_medium"])
    long_count = sum(1 for r in results if r["is_long"])

    return AnalysisResult(
        avg_response_length=avg_len,
        avg_line_count=avg_lines,
        markdown_usage=avg_md,
        formal_ratio=avg_formal,
        technical_ratio=avg_tech,
        brief_ratio=brief_count / len(results) if results else 0,
        code_block_count=sum(r["code_blocks"] for r in results),
        emoji_count=sum(r["emojis"] for r in results),
        question_count=sum(r["questions"] for r in results),
        total_samples=len(results),
    )


def _analysis_to_profile(analysis: AnalysisResult) -> dict[str, Any]:
    """Convert analysis results to a model profile dict."""
    # Determine communication style
    if analysis.technical_ratio > 0.15 or analysis.code_block_count > 2:
        comm_style = "technical"
    elif analysis.formal_ratio > 0.03:
        comm_style = "detailed"
    else:
        comm_style = "brief"

    # Determine preferred length
    if analysis.brief_ratio > 0.6:
        pref_length = "short"
    elif analysis.brief_ratio > 0.3 and analysis.avg_response_length > 100:
        pref_length = "long"
    else:
        pref_length = "medium"

    # Determine format preference
    if analysis.markdown_usage > 0.5:
        fmt_pref = "markdown"
    elif analysis.code_block_count > 2:
        fmt_pref = "structured"
    else:
        fmt_pref = "plain"

    # Determine tone
    if analysis.technical_ratio > 0.2:
        tone = "technical"
    elif analysis.formal_ratio > 0.05:
        tone = "formal"
    else:
        tone = "casual"

    return {
        "communication_style": comm_style,
        "preferred_length": pref_length,
        "format_preference": fmt_pref,
        "tone": tone,
    }


def save_profile_to_db(
    model_id: str,
    communication_style: str,
    preferred_length: str,
    format_preference: str,
    tone: str,
) -> str:
    """Save or update a model profile in the database."""
    profile_id = str(uuid.uuid4())
    now = int(time.time())

    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO model_profiles
            (id, model_id, communication_style, preferred_length, format_preference, tone, created_at, updated_at)
            VALUES (
                COALESCE((SELECT id FROM model_profiles WHERE model_id = ?), ?),
                ?, ?, ?, ?, ?, ?, ?
            )
        """, (model_id, profile_id, model_id, communication_style, preferred_length, format_preference, tone, now, now))

    return model_id


def analyze_and_save_profile(samples_dir: Path, model_id: str) -> dict[str, Any]:
    """Run full analysis and save results both to DB and JSON file."""
    analysis = analyze_samples(samples_dir)
    profile = _analysis_to_profile(analysis)
    profile["model_id"] = model_id
    profile["analysis_stats"] = {
        "avg_response_length": round(analysis.avg_response_length, 1),
        "avg_line_count": round(analysis.avg_line_count, 1),
        "markdown_usage": round(analysis.markdown_usage, 3),
        "formal_ratio": round(analysis.formal_ratio, 4),
        "technical_ratio": round(analysis.technical_ratio, 4),
        "code_block_count": analysis.code_block_count,
        "emoji_count": analysis.emoji_count,
        "question_count": analysis.question_count,
        "total_samples": analysis.total_samples,
    }

    # Save to JSON file
    profile_file = PROFILES_DIR / f"{model_id}.json"
    profile_file.parent.mkdir(parents=True, exist_ok=True)
    profile_file.write_text(json.dumps(profile, indent=2, ensure_ascii=False))

    # Save to DB
    save_profile_to_db(
        model_id=model_id,
        communication_style=profile["communication_style"],
        preferred_length=profile["preferred_length"],
        format_preference=profile["format_preference"],
        tone=profile["tone"],
    )

    return profile


def load_profile(model_id: str) -> dict[str, Any] | None:
    """Load a model profile from JSON file."""
    profile_file = PROFILES_DIR / f"{model_id}.json"
    if not profile_file.exists():
        # Try DB
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM model_profiles WHERE model_id = ?", (model_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    return json.loads(profile_file.read_text())


def list_profiles() -> list[dict[str, Any]]:
    """List all saved profiles."""
    profiles = []
    for f in PROFILES_DIR.glob("*.json"):
        try:
            profiles.append(json.loads(f.read_text()))
        except Exception:
            pass
    return profiles
