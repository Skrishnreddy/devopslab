"""Learn Mode: structured tracks and modules with progress."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db
from ..services import content

router = APIRouter(prefix="/api/learn", tags=["learn"])


def _with_progress(track: dict, done: dict[str, str]) -> dict:
    modules = [{**m, "completed": m["id"] in done} for m in track.get("modules", [])]
    total = len(modules)
    completed = sum(m["completed"] for m in modules)
    return {
        **track,
        "modules": modules,
        "progress": {"completed": completed, "total": total,
                     "percent": round(100 * completed / total) if total else 0},
    }


@router.get("/tracks")
def list_tracks():
    done = db.completed_modules()
    return [_with_progress(t, done) for t in content.tracks()]


@router.get("/tracks/{track_id}")
def get_track(track_id: str):
    done = db.completed_modules()
    for t in content.tracks():
        if t["id"] == track_id:
            return _with_progress(t, done)
    raise HTTPException(404, "track not found")


class CompleteBody(BaseModel):
    completed: bool = True


@router.post("/modules/{module_id}/complete")
def complete_module(module_id: str, body: CompleteBody):
    found = content.find_module(module_id)
    if not found:
        raise HTTPException(404, "module not found")
    track, _ = found
    db.set_module_complete(module_id, track["id"], body.completed)
    return {"module_id": module_id, "completed": body.completed}
