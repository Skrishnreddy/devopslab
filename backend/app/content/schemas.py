"""Write JSON Schemas for contributors: python -m app.content.schemas"""
import json
import sys
from pathlib import Path

from ..core.config import settings
from .models import Challenge, Lesson, Project, Track

MODELS = {"track": Track, "project": Project, "challenge": Challenge, "lesson": Lesson}


def render() -> dict[str, str]:
    return {f"{name}.schema.json": json.dumps(m.model_json_schema(), indent=2) + "\n" for name, m in MODELS.items()}


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else settings.content_dir / "schemas"
    out.mkdir(parents=True, exist_ok=True)
    for fname, text in render().items():
        (out / fname).write_text(text)
        print(f"wrote {out / fname}")
