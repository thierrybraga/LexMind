"""
Serviço de integração Backend FastAPI ↔ Apache Airflow.
Permite ao backend disparar DAGs e monitorar execuções.
"""

import httpx
from datetime import datetime
from typing import Optional
from app.core.config import settings


class AirflowService:
    """Cliente para a API REST do Airflow."""

    def __init__(self):
        self.base_url = getattr(settings, "AIRFLOW_URL", "http://airflow-webserver:8080")
        self.username = getattr(settings, "AIRFLOW_USERNAME", "admin")
        self.password = getattr(settings, "AIRFLOW_PASSWORD", "admin")

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.username, self.password),
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    async def trigger_dag(
        self,
        dag_id: str,
        conf: Optional[dict] = None,
        logical_date: Optional[str] = None,
    ) -> dict:
        """Dispara uma DAG run."""
        payload = {
            "conf": conf or {},
            "note": f"Triggered by IA Jurídica at {datetime.now().isoformat()}",
        }
        if logical_date:
            payload["logical_date"] = logical_date

        async with self._get_client() as client:
            response = await client.post(
                f"/api/v1/dags/{dag_id}/dagRuns",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def trigger_peticao_generation(self, peticao_id: int) -> dict:
        """Dispara geração de petição via Airflow."""
        return await self.trigger_dag(
            dag_id="gerar_peticao_llm",
            conf={"peticao_id": str(peticao_id)},
        )

    async def get_dag_status(self, dag_id: str, dag_run_id: str) -> dict:
        """Consulta status de uma DAG run."""
        async with self._get_client() as client:
            response = await client.get(
                f"/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}"
            )
            response.raise_for_status()
            return response.json()

    async def get_dag_runs(self, dag_id: str, limit: int = 10) -> dict:
        """Lista execuções recentes de uma DAG."""
        async with self._get_client() as client:
            response = await client.get(
                f"/api/v1/dags/{dag_id}/dagRuns",
                params={"limit": limit, "order_by": "-execution_date"},
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> dict:
        """Verifica saúde do Airflow."""
        try:
            async with self._get_client() as client:
                response = await client.get("/health")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Singleton
airflow_service = AirflowService()
