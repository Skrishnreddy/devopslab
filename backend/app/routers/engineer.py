"""Engineer Mode: pre-deployed projects, incidents and lab resets."""
from fastapi import APIRouter, HTTPException

from ..services import content, lab_engine

router = APIRouter(prefix="/api/engineer", tags=["engineer"])


@router.get("/projects")
def list_projects():
    return content.projects()


@router.post("/labs/{lab_id}/reset")
def reset_lab(lab_id: str):
    try:
        return lab_engine.reset(lab_id)
    except lab_engine.LabError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/labs/{lab_id}/deploy")
def deploy_lab(lab_id: str):
    try:
        return {"lab": lab_id, "applied": lab_engine.deploy(lab_id).strip().splitlines()}
    except lab_engine.LabError as e:
        raise HTTPException(409, str(e)) from e
