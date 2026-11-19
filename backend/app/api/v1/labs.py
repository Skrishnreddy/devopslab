"""Lab management (Phase 4): deploy, stop, start, reset, delete, status and usage."""
import asyncio

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from ...auth.deps import Principal, current_principal
from ...content.loader import get_content
from ...core.errors import AppError
from ...db.models import Lab
from ...db.session import get_db
from ...providers import registry
from ...providers.cluster import ClusterAPIError, ClusterUnavailable
from ...providers.lab_service import LabConflict
from ...providers.labs import LabError

router = APIRouter(prefix="/labs", tags=["labs"])
LabId = Path(pattern=r"^[a-z0-9][a-z0-9-]{0,40}$")


def _project_lab(ref_id: str) -> str:
    project = next((p for p in get_content().projects if p.lab == ref_id), None)
    if project is None:
        raise AppError(404, "not_found", f"No deployable lab '{ref_id}'")
    return ref_id


def _owned(db: DB, lab_id: str, user_id: int) -> Lab | None:
    lab = db.get(Lab, lab_id)
    return lab if lab is not None and lab.user_id == user_id else None


@router.get("")
def list_labs(p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    """Every deployable lab, deployed or not, with its live operation."""
    svc = registry.labs()
    rows = {lab.ref_id: lab for lab in db.scalars(select(Lab).where(Lab.user_id == p.user.id))}
    return [svc.view(rows.get(pr.lab), pr.lab) for pr in get_content().projects if pr.lab]


@router.get("/{lab_id}")
def get_lab(lab_id: str = LabId, p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    ref = _project_lab(lab_id)
    return registry.labs().view(_owned(db, lab_id, p.user.id), ref)


class DeployBody(BaseModel):
    ref_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,40}$")


async def _start(db: DB, p: Principal, ref: str, action: str) -> dict:
    svc = registry.labs()
    try:
        svc.start_operation(db, p.user.id, ref, action)
    except LabConflict as e:
        raise AppError(409, "lab_busy", str(e)) from e
    except LabError as e:
        raise AppError(400, "lab_invalid", str(e)) from e
    await asyncio.sleep(0)  # let the first step register
    return svc.view(_owned(db, svc.lab_id(ref), p.user.id), ref)


@router.post("", status_code=202)
async def deploy(body: DeployBody, p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    return await _start(db, p, _project_lab(body.ref_id), "deploy")


@router.post("/{lab_id}/{action}", status_code=202)
async def act(action: str, lab_id: str = LabId, p: Principal = Depends(current_principal),
              db: DB = Depends(get_db)):
    ref = _project_lab(lab_id)
    if action == "extend":
        lab = _owned(db, lab_id, p.user.id)
        if lab is None or lab.status != "running":
            raise AppError(409, "lab_busy", "Only a running lab can be extended")
        registry.labs().extend(db, lab)
        return registry.labs().view(lab, ref)
    if action not in {"start", "stop", "reset"}:
        raise AppError(404, "not_found", f"Unknown lab action '{action}'")
    return await _start(db, p, ref, action)


@router.delete("/{lab_id}", status_code=202)
async def delete(lab_id: str = LabId, p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    return await _start(db, p, _project_lab(lab_id), "delete")


@router.get("/{lab_id}/usage")
def usage(lab_id: str = LabId, p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    lab = _owned(db, lab_id, p.user.id)
    if lab is None or not lab.namespaces:
        raise AppError(404, "not_found", "This lab isn't deployed")
    try:
        return registry.cluster().usage(lab.namespaces)
    except ClusterUnavailable as e:
        raise AppError(503, "cluster_unreachable", str(e)) from e
    except ClusterAPIError as e:
        raise AppError(502, "kubernetes_error", e.message) from e
