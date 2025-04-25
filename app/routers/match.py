from fastapi import APIRouter, HTTPException, Body, status
from app.utils.supabase_utils import search_resumes_by_vector
from app.utils.embedding_utils import get_embedding
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/match", tags=["Matching"])


@router.post("/jd")
async def match_resumes_with_jd(
        job_description: str = Body(..., embed=True, description="The full text of the job description."),
        match_threshold: float = Body(0.7, embed=True,
                                      description="Minimum similarity score (0.0 to 1.0) for a resume to be considered a match."),
        match_count: int = Body(10, embed=True, description="Maximum number of matched resumes to return.")
) -> Dict[str, Any]:
    """
    Matches resumes from the database against a given job description using vector similarity search.

    Requires the Supabase 'match_resumes' DB function to be set up.
    """
    if not job_description:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job description cannot be empty.")
    if not (0.0 <= match_threshold <= 1.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Match threshold must be between 0.0 and 1.0.")
    if match_count <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Match count must be positive.")

    try:
        logger.info(
            f"Matching JD (length: {len(job_description)}) with threshold: {match_threshold}, count: {match_count}")
        # 1. Generate embedding for the job description
        jd_embedding = get_embedding(job_description)
        logger.info("JD embedding generated.")

        # 2. Call Supabase function to find similar resumes
        # This function now takes the embedding, threshold, and count
        matched_docs = await search_resumes_by_vector(
            jd_embedding=jd_embedding,
            match_threshold=match_threshold,
            match_count=match_count
        )
        logger.info(f"Received {len(matched_docs)} potential matches from vector search.")

        # 3. Format results (Supabase function returns id, filename, file_url, similarity)
        results = [
            {
                "id": resume.get("id"),
                "filename": resume.get("filename"),
                "file_url": resume.get("file_url"),
                # Convert similarity (0-1) to percentage score (0-100)
                "score": round(resume.get("similarity", 0) * 100, 2)
            }
            for resume in matched_docs  # matched_docs is already sorted by similarity DESC by the DB function
        ]

        # Sorting is already done by the database function, but uncomment if needed
        # results = sorted(results, key=lambda x: x["score"], reverse=True)

        return {
            "job_description_preview": job_description[:200] + "..." if len(job_description) > 200 else job_description,
            "match_threshold": match_threshold,
            "match_count": len(results),  # Actual number returned
            "matched_resumes": results
        }

    except HTTPException as he:
        raise he  # Re-raise validation errors etc.
    except Exception as e:
        logger.error(f"Error during JD matching: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during matching: {e}"
        )

