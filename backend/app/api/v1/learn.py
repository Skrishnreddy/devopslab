from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from ...auth.deps import Principal, current_principal
from ...content.loader import get_content
from ...content.models import Track
from ...core.errors import AppError
from ...db.models import Activity, ModuleProgress
from ...db.session import get_db

router = APIRouter(prefix="/learn", tags=["learn"])


def _progress_map(db: DB, user_id: int) -> dict[str, ModuleProgress]:
    return {p.module_id: p for p in db.scalars(select(ModuleProgress).where(ModuleProgress.user_id == user_id))}


def track_view(track: Track, progress: dict[str, ModuleProgress]) -> dict:
    modules = []
    for m in track.modules:
        p = progress.get(m.id)
        modules.append({**m.model_dump(), "status": p.status if p else "not_started",
                        "completed_at": p.completed_at if p else None})
    total = len(modules)
    done = sum(m["status"] == "completed" for m in modules)
    return {**track.model_dump(exclude={"modules"}), "modules": modules,
            "progress": {"completed": done, "total": total, "percent": round(100 * done / total) if total else 0}}


@router.get("/tracks")
def tracks(p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    progress = _progress_map(db, p.user.id)
    return [track_view(t, progress) for t in get_content().tracks]


@router.get("/tracks/{track_id}")
def track(track_id: str, p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    for t in get_content().tracks:
        if t.id == track_id:
            return track_view(t, _progress_map(db, p.user.id))
    raise AppError(404, "not_found", f"Track '{track_id}' not found")


class ProgressBody(BaseModel):
    status: Literal["not_started", "started", "completed"]


@router.put("/modules/{module_id}/progress")
def set_progress(module_id: str, body: ProgressBody, p: Principal = Depends(current_principal),
                 db: DB = Depends(get_db)):
    found = get_content().module(module_id)
    if not found:
        raise AppError(404, "not_found", f"Module '{module_id}' not found")
    track, module = found
    row = db.scalar(select(ModuleProgress).where(ModuleProgress.user_id == p.user.id,
                                                 ModuleProgress.module_id == module_id))
    if body.status == "not_started":
        if row:
            db.delete(row)
        db.commit()
        return {"module_id": module_id, "status": "not_started", "completed_at": None}
    now = datetime.now(UTC)
    if row is None:
        row = ModuleProgress(user_id=p.user.id, module_id=module_id, track_id=track.id, status=body.status)
        db.add(row)
    row.status = body.status
    row.completed_at = now if body.status == "completed" else None
    db.add(Activity(user_id=p.user.id, kind="module", ref_id=module_id, title=f"{track.name}: {module.title}"))
    db.commit()
    return {"module_id": module_id, "status": row.status, "completed_at": row.completed_at}
