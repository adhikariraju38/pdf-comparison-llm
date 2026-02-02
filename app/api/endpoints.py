"""
API endpoints for PDF comparison service.
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Dict
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime
import logging

from app.models.schemas import (
    ComparisonResponse, JobStatus, ComparisonResult,
    LLMConfig, HealthResponse, ErrorResponse
)
from app.services.comparison_engine import ComparisonEngine
from app.services.pdf_generator import PDFGenerator
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job storage (in production, use Redis or a database)
jobs: Dict[str, Dict] = {}


def process_comparison(
    job_id: str,
    source_path: str,
    copy_path: str,
    llm_config: LLMConfig
):
    """
    Background task to process PDF comparison.

    Args:
        job_id: Unique job identifier
        source_path: Path to source PDF
        copy_path: Path to copy PDF
        llm_config: LLM configuration
    """
    try:
        logger.info(f"Starting comparison job {job_id}")

        def update_progress(step: str, progress: int):
            jobs[job_id]["current_step"] = step
            jobs[job_id]["progress"] = progress
            logger.debug(f"Job {job_id}: {step} ({progress}%)")

        # Update job status
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["current_step"] = "Initializing..."
        jobs[job_id]["progress"] = 0

        # Run comparison
        engine = ComparisonEngine(source_path, copy_path, llm_config)
        page_analyses, summary = engine.compare(progress_callback=update_progress)

        # Generate output PDF
        output_path = str(Path(settings.output_dir) / f"{job_id}_comparison.pdf")
        generator = PDFGenerator(source_path, copy_path, output_path, dpi=settings.comparison_dpi)
        generator.generate(page_analyses, summary, progress_callback=update_progress)

        # Collect all differences
        all_differences = []
        for analysis in page_analyses:
            all_differences.extend(analysis.differences)

        # Update job with results
        jobs[job_id].update({
            "status": "completed",
            "progress": 100,
            "current_step": "Complete",
            "output_pdf_url": f"/api/download/{job_id}",
            "summary": summary.model_dump(),
            "differences": [d.model_dump() for d in all_differences],
            "page_analyses": [a.model_dump() for a in page_analyses],
            "completed_at": datetime.now().isoformat()
        })

        logger.info(f"Comparison job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Error in job {job_id}: {e}", exc_info=True)
        jobs[job_id].update({
            "status": "failed",
            "error": str(e),
            "current_step": "Failed"
        })


@router.post("/compare", response_model=ComparisonResponse)
async def compare_pdfs(
    background_tasks: BackgroundTasks,
    source_file: UploadFile = File(..., description="Source PDF file"),
    copy_file: UploadFile = File(..., description="Copy PDF file"),
    llm_config: str = Form(..., description="LLM configuration as JSON string")
):
    """
    Upload two PDFs and start comparison job.

    Args:
        source_file: Source PDF file
        copy_file: Copy PDF file
        llm_config: JSON string with LLM configuration

    Returns:
        ComparisonResponse with job_id
    """
    # Generate job ID
    job_id = str(uuid.uuid4())

    try:
        # Parse LLM config
        try:
            llm_config_dict = json.loads(llm_config)
            llm_config_obj = LLMConfig(**llm_config_dict)
        except (json.JSONDecodeError, Exception) as e:
            raise HTTPException(status_code=400, detail=f"Invalid LLM config: {e}")

        # Validate file types
        if not source_file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Source file must be a PDF")
        if not copy_file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Copy file must be a PDF")

        # Create upload directory if it doesn't exist
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        output_dir = Path(settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded files
        source_path = upload_dir / f"{job_id}_source.pdf"
        copy_path = upload_dir / f"{job_id}_copy.pdf"

        with source_path.open("wb") as f:
            shutil.copyfileobj(source_file.file, f)

        with copy_path.open("wb") as f:
            shutil.copyfileobj(copy_file.file, f)

        logger.info(f"Created job {job_id}: {source_file.filename} vs {copy_file.filename}")

        # Initialize job status
        jobs[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "progress": 0,
            "current_step": "Queued",
            "error": None,
            "created_at": datetime.now().isoformat(),
            "source_filename": source_file.filename,
            "copy_filename": copy_file.filename
        }

        # Start background task
        background_tasks.add_task(
            process_comparison,
            job_id,
            str(source_path),
            str(copy_path),
            llm_config_obj
        )

        return ComparisonResponse(
            job_id=job_id,
            status="processing",
            message="Comparison started"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating comparison job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start comparison: {e}")


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    Get status of a comparison job.

    Args:
        job_id: Job identifier

    Returns:
        JobStatus with current status and progress
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress", 0),
        current_step=job.get("current_step"),
        error=job.get("error")
    )


@router.get("/result/{job_id}", response_model=ComparisonResult)
async def get_comparison_result(job_id: str):
    """
    Get comparison results for a completed job.

    Args:
        job_id: Job identifier

    Returns:
        ComparisonResult with summary and differences
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (status: {job['status']})"
        )

    from app.models.schemas import ComparisonSummary
    summary = ComparisonSummary(**job["summary"])

    return ComparisonResult(
        job_id=job_id,
        output_pdf_url=job["output_pdf_url"],
        summary=summary,
        differences=job["differences"],
        page_analyses=job.get("page_analyses")
    )


@router.get("/download/{job_id}")
async def download_comparison_pdf(job_id: str):
    """
    Download the comparison PDF.

    Args:
        job_id: Job identifier

    Returns:
        FileResponse with PDF file
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (status: {job['status']})"
        )

    # Construct output path
    output_path = Path(settings.output_dir) / f"{job_id}_comparison.pdf"

    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output PDF not found")

    return FileResponse(
        path=str(output_path),
        media_type="application/pdf",
        filename=f"comparison_{job_id}.pdf"
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        HealthResponse with status and version
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.now().isoformat()
    )
