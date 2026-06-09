import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)
JOBS_FILE = Path("data/jobs.json")


class JobService:
    """
    Simple background job tracker.
    Stores job status in data/jobs.json.
    
    States: pending → processing → completed / failed
    """

    def _load(self) -> Dict:
        if not JOBS_FILE.exists():
            return {"jobs": {}}
        with open(JOBS_FILE) as f:
            return json.load(f)

    def _save(self, data: Dict):
        JOBS_FILE.parent.mkdir(exist_ok=True)
        with open(JOBS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def create_job(self, job_id: str, tenant_id: str, filename: str) -> Dict:
        data = self._load()
        job = {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "filename": filename,
            "status": "pending",
            "result": None,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }
        data["jobs"][job_id] = job
        self._save(data)
        return job

    def update_job(self, job_id: str, status: str, result=None, error=None):
        data = self._load()
        if job_id in data["jobs"]:
            data["jobs"][job_id]["status"] = status
            data["jobs"][job_id]["result"] = result
            data["jobs"][job_id]["error"] = error
            if status in ("completed", "failed"):
                data["jobs"][job_id]["completed_at"] = datetime.utcnow().isoformat()
            self._save(data)

    def get_job(self, job_id: str) -> Optional[Dict]:
        return self._load()["jobs"].get(job_id)