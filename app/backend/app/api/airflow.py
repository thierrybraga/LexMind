"""
API Router para integração com Apache Airflow.
Endpoints para disparar DAGs e monitorar execuções.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.security import get_current_user, require_role
from app.services.airflow_service import airflow_service


router = APIRouter(prefix="/api/airflow", tags=["airflow"])


class TriggerDAGRequest(BaseModel):
    dag_id: str
    conf: Optional[dict] = None


class TriggerPeticaoRequest(BaseModel):
    peticao_id: int


# ─── Endpoints ────────────────────────────────────────────


@router.get("/health")
async def airflow_health(current_user=Depends(get_current_user)):
    """Verifica saúde do Airflow."""
    return await airflow_service.health_check()


@router.post("/trigger")
async def trigger_dag(
    request: TriggerDAGRequest,
    current_user=Depends(require_role(["admin"])),
):
    """Dispara uma DAG (somente admin)."""
    try:
        result = await airflow_service.trigger_dag(
            dag_id=request.dag_id,
            conf=request.conf,
        )
        return {"status": "triggered", "dag_run": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gerar-peticao")
async def trigger_peticao(
    request: TriggerPeticaoRequest,
    current_user=Depends(get_current_user),
):
    """Dispara geração de petição via Airflow."""
    try:
        result = await airflow_service.trigger_peticao_generation(request.peticao_id)
        return {"status": "processing", "dag_run_id": result.get("dag_run_id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dags/{dag_id}/runs")
async def list_dag_runs(
    dag_id: str,
    limit: int = 10,
    current_user=Depends(require_role(["admin"])),
):
    """Lista execuções de uma DAG (somente admin)."""
    try:
        return await airflow_service.get_dag_runs(dag_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dags/{dag_id}/runs/{dag_run_id}")
async def get_dag_run_status(
    dag_id: str,
    dag_run_id: str,
    current_user=Depends(get_current_user),
):
    """Consulta status de uma execução."""
    try:
        return await airflow_service.get_dag_status(dag_id, dag_run_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
