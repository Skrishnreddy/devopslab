import json
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
from ...db.models import Activity, ExerciseAttempt, ModuleProgress
from ...db.session import get_db
from ...learning import exercises as ex_ops
from ...learning.checks import NAMESPACE, CheckRunner
from ...providers import registry
from ...providers.cluster import ClusterUnavailable
from ...providers.labs import LabError

router = APIRouter(prefix="/learn", tags=["learn"])


def _progress_map(db: DB, user_id: int) -> dict[str, ModuleProgress]:
    return {p.module_id: p for p in db.scalars(select(ModuleProgress).where(ModuleProgress.user_id == user_id))}


def track_view(track: Track, progress: dict[str, ModuleProgress]) -> dict:
    modules = []
    for m in track.modules:
        p = progress.get(m.id)
        modules.append({**m.model_dump(), "status": p.status if p else "not_started",
                        "completed_at": p.completed_at if p else None,
                        "lesson": m.id in get_content().lessons})
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


# ---- lessons, exercises and quizzes (Phase 5) ---------------------------------
QUIZ = "quiz"  # exercise_id under which quiz results are stored
QUIZ_PASS_PERCENT = 70


def _lesson(module_id: str):
    found = get_content().module(module_id)
    lesson = get_content().lessons.get(module_id)
    if not found:
        raise AppError(404, "not_found", f"Module '{module_id}' not found")
    if lesson is None:
        raise AppError(404, "not_found", f"Module '{module_id}' has no lesson yet (Planned)")
    return found[0], found[1], lesson


def _exercise(lesson, exercise_id: str):
    for e in lesson.exercises:
        if e.id == exercise_id:
            return e
    raise AppError(404, "not_found", f"Exercise '{exercise_id}' not found")


def _attempts(db: DB, user_id: int, module_id: str) -> list[ExerciseAttempt]:
    return list(db.scalars(select(ExerciseAttempt).where(ExerciseAttempt.user_id == user_id,
                                                         ExerciseAttempt.module_id == module_id)
                           .order_by(ExerciseAttempt.attempted_at, ExerciseAttempt.id)))


def _set_status(db: DB, user_id: int, track, module, status: str) -> ModuleProgress:
    row = db.scalar(select(ModuleProgress).where(ModuleProgress.user_id == user_id,
                                                 ModuleProgress.module_id == module.id))
    if row is None:
        row = ModuleProgress(user_id=user_id, module_id=module.id, track_id=track.id, status=status)
        db.add(row)
    if row.status != status:
        row.status = status
        row.completed_at = datetime.now(UTC) if status == "completed" else None
        db.add(Activity(user_id=user_id, kind="module", ref_id=module.id,
                        title=f"{track.name}: {module.title} {'completed' if status == 'completed' else 'started'}"))
    return row


def _progress(db: DB, user_id: int, track, module, lesson) -> str:
    """started on the first attempt; completed once every exercise has passed and the quiz is passed."""
    attempts = _attempts(db, user_id, module.id)
    passed = {a.exercise_id for a in attempts if a.passed}
    row = db.scalar(select(ModuleProgress).where(ModuleProgress.user_id == user_id,
                                                 ModuleProgress.module_id == module.id))
    if all(e.id in passed for e in lesson.exercises) and QUIZ in passed:
        return _set_status(db, user_id, track, module, "completed").status
    if row is None:
        return _set_status(db, user_id, track, module, "started").status
    return row.status


def _exercise_view(e, attempts: list[ExerciseAttempt]) -> dict:
    mine = [a for a in attempts if a.exercise_id == e.id]
    last = mine[-1] if mine else None
    return {**e.model_dump(exclude={"solution", "checks", "setup", "cleanup"}),
            "has_setup": bool(e.setup),
            "checks": [c.description for c in e.checks],
            "passed": any(a.passed for a in mine),
            "last": {"passed": last.passed, "at": last.attempted_at,
                     "results": json.loads(last.output_summary or "[]")} if last else None}


@router.get("/modules/{module_id}")
def module_lesson(module_id: str, p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    """A lesson without quiz answers or exercise solutions; those come only from the endpoints below."""
    track, module, lesson = _lesson(module_id)
    attempts = _attempts(db, p.user.id, module_id)
    quiz = [a for a in attempts if a.exercise_id == QUIZ]
    row = _progress_map(db, p.user.id).get(module_id)
    best = max((json.loads(a.output_summary or "{}").get("percent", 0) for a in quiz), default=None)
    return {**module.model_dump(), "track_id": track.id, "track_name": track.name,
            "status": row.status if row else "not_started", "namespace": NAMESPACE,
            "lesson": {**lesson.model_dump(exclude={"exercises", "quiz", "id"})},
            "exercises": [_exercise_view(e, attempts) for e in lesson.exercises],
            "quiz": {"questions": [{"question": q.question, "options": q.options} for q in lesson.quiz],
                     "best_percent": best, "passed": any(a.passed for a in quiz),
                     "pass_percent": QUIZ_PASS_PERCENT}}


@router.post("/modules/{module_id}/exercises/{exercise_id}/check")
def check_exercise(module_id: str, exercise_id: str, p: Principal = Depends(current_principal),
                   db: DB = Depends(get_db)):
    track, module, lesson = _lesson(module_id)
    exercise = _exercise(lesson, exercise_id)
    cluster = registry.cluster()
    try:
        results = CheckRunner(cluster.raw_get).run_all(exercise.checks)
    except ClusterUnavailable as e:
        raise AppError(503, "cluster_unreachable", str(e)) from e
    passed = all(r["passed"] for r in results)
    now = datetime.now(UTC)
    db.add(ExerciseAttempt(user_id=p.user.id, module_id=module_id, exercise_id=exercise_id, passed=passed,
                           output_summary=json.dumps(results), attempted_at=now))
    db.flush()
    status = _progress(db, p.user.id, track, module, lesson)
    db.commit()
    return {"passed": passed, "results": results, "at": now, "module_status": status}


def _kubectl_op(fn, exercise) -> list[str]:
    try:
        return fn(exercise)
    except LabError as e:
        raise AppError(502, "kubernetes_error", f"{e.step}: {e}") from e


@router.post("/modules/{module_id}/exercises/{exercise_id}/reset")
def reset_exercise(module_id: str, exercise_id: str, p: Principal = Depends(current_principal)):
    """Delete what this exercise creates in lab-playground and re-apply its starting state."""
    _, _, lesson = _lesson(module_id)
    return {"namespace": NAMESPACE, "output": _kubectl_op(ex_ops.reset, _exercise(lesson, exercise_id))}


@router.post("/modules/{module_id}/exercises/{exercise_id}/setup")
def setup_exercise(module_id: str, exercise_id: str, p: Principal = Depends(current_principal)):
    _, _, lesson = _lesson(module_id)
    exercise = _exercise(lesson, exercise_id)
    if not exercise.setup:
        raise AppError(409, "no_setup", "This exercise starts from an empty namespace")
    return {"namespace": NAMESPACE, "output": _kubectl_op(ex_ops.setup, exercise)}


@router.get("/modules/{module_id}/exercises/{exercise_id}/solution")
def solution(module_id: str, exercise_id: str, p: Principal = Depends(current_principal)):
    _, _, lesson = _lesson(module_id)
    return {"solution": _exercise(lesson, exercise_id).solution}


class QuizBody(BaseModel):
    answers: list[int]


@router.post("/modules/{module_id}/quiz")
def submit_quiz(module_id: str, body: QuizBody, p: Principal = Depends(current_principal),
                db: DB = Depends(get_db)):
    track, module, lesson = _lesson(module_id)
    if len(body.answers) != len(lesson.quiz):
        raise AppError(422, "invalid_answers", f"Expected {len(lesson.quiz)} answers, got {len(body.answers)}")
    results = [{"correct": a == q.answer, "answer": q.answer, "explanation": q.explanation}
               for a, q in zip(body.answers, lesson.quiz, strict=True)]
    score = sum(r["correct"] for r in results)
    percent = round(100 * score / len(results))
    passed = percent >= QUIZ_PASS_PERCENT
    db.add(ExerciseAttempt(user_id=p.user.id, module_id=module_id, exercise_id=QUIZ, passed=passed,
                           output_summary=json.dumps({"score": score, "percent": percent})))
    db.flush()
    status = _progress(db, p.user.id, track, module, lesson)
    db.commit()
    return {"score": score, "total": len(results), "percent": percent, "passed": passed, "results": results,
            "module_status": status}
