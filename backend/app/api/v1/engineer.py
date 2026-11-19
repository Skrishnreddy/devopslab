"""Projects catalog, labs, challenge attempts, progress and activity (read side)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from ...auth.deps import Principal, current_principal
from ...content.loader import get_content
from ...db.models import Activity, ChallengeAttempt, ModuleProgress
from ...db.session import get_db

router = APIRouter(tags=["engineer"])


@router.get("/projects")
def projects(_: Principal = Depends(current_principal)):
    return [p.model_dump() for p in get_content().projects]


@router.get("/challenges")
def challenges(_: Principal = Depends(current_principal)):
    return [c.model_dump(include={"id", "name", "difficulty", "technology", "status", "phase", "description",
                                  "skills"}) for c in get_content().challenges]


@router.get("/challenges/attempts")
def attempts(limit: int = Query(10, ge=1, le=100), p: Principal = Depends(current_principal),
             db: DB = Depends(get_db)):
    names = {c.id: c.name for c in get_content().challenges}
    q = (select(ChallengeAttempt).where(ChallengeAttempt.user_id == p.user.id)
         .order_by(ChallengeAttempt.started_at.desc()).limit(limit))
    return [{"id": a.id, "challenge_id": a.challenge_id, "name": names.get(a.challenge_id, a.challenge_id),
             "status": a.status, "hints_used": a.hints_used, "started_at": a.started_at,
             "finished_at": a.finished_at} for a in db.scalars(q)]


@router.get("/progress/summary")
def progress_summary(p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    content = get_content()
    modules = {m.id: m for t in content.tracks for m in t.modules}
    rows = list(db.scalars(select(ModuleProgress).where(ModuleProgress.user_id == p.user.id)))
    completed = [r for r in rows if r.status == "completed" and r.module_id in modules]
    attempts = list(db.scalars(select(ChallengeAttempt).where(ChallengeAttempt.user_id == p.user.id)))
    passed = [a for a in attempts if a.status == "passed"]
    skills = sorted({s for r in completed for s in modules[r.module_id].skills}
                    | {s for a in passed for c in content.challenges if c.id == a.challenge_id for s in c.skills})
    seconds = sum(r.time_spent_seconds for r in rows) + sum(
        int((a.finished_at - a.started_at).total_seconds()) for a in attempts if a.finished_at)
    total = len(modules)
    return {
        "overall_percent": round(100 * len(completed) / total) if total else 0,
        "modules_completed": len(completed),
        "modules_total": total,
        "challenges_passed": len(passed),
        "challenges_failed": sum(a.status == "failed" for a in attempts),
        "hints_used": sum(a.hints_used for a in attempts),
        "learning_seconds": seconds,
        "skills": skills,
    }


@router.get("/activity/recent")
def recent(kind: str | None = None, limit: int = Query(5, ge=1, le=50),
           p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    # Newest entry per (kind, ref_id), newest first.
    latest = (select(Activity.kind, Activity.ref_id, func.max(Activity.id).label("id"))
              .where(Activity.user_id == p.user.id).group_by(Activity.kind, Activity.ref_id).subquery())
    q = select(Activity).join(latest, Activity.id == latest.c.id).order_by(Activity.id.desc()).limit(limit)
    if kind:
        q = q.where(Activity.kind == kind)
    return [{"kind": a.kind, "ref_id": a.ref_id, "title": a.title, "at": a.at} for a in db.scalars(q)]
