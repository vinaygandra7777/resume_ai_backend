from fastapi import APIRouter, HTTPException, status, Body
from app.utils.supabase_utils import search_resumes_by_vector, get_all_resumes_from_db # Keep get_all if needed elsewhere
from app.utils.embedding_utils import get_embedding
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["Analyze"])

# Note: The original app/utils/analyzer.py file is no longer needed and should be deleted.

@router.post("/resumes")
async def analyze_all_resumes(
    job_description: str = Body(..., embed=True, description="The full text of the job description."),
    min_score_threshold: float = Body(0.5, embed=True, description="Minimum similarity score (0.0 to 1.0) to include in analysis."),
    max_results: int = Body(50, embed=True, description="Maximum number of resumes to retrieve for analysis.")
    ) -> Dict[str, Any]:
    """
    Retrieves resumes matching a job description using vector similarity
    and returns their scores. Placeholder for future RAG-based feedback.

    Requires the Supabase 'match_resumes' DB function to be set up.
    """
    if not job_description:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job description cannot be empty.")
    if not (0.0 <= min_score_threshold <= 1.0):
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Minimum score threshold must be between 0.0 and 1.0.")
    if max_results <= 0:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Max results must be positive.")

    try:
        logger.info(f"Analyzing resumes against JD (length: {len(job_description)}). Threshold: {min_score_threshold}, Max Results: {max_results}")
        # 1. Generate embedding for the job description
        jd_embedding = get_embedding(job_description)
        logger.info("JD embedding generated.")

        # 2. Call Supabase function to find similar resumes
        matched_docs = await search_resumes_by_vector(
            jd_embedding=jd_embedding,
            match_threshold=min_score_threshold, # Use the analysis threshold
            match_count=max_results # Limit the number of results
        )
        logger.info(f"Retrieved {len(matched_docs)} resumes for analysis based on vector search.")

        if not matched_docs:
            # Return empty results cleanly instead of 404 if search just yields nothing
             return {
                "job_description_preview": job_description[:200] + "..." if len(job_description) > 200 else job_description,
                "analysis_threshold": min_score_threshold,
                "analyzed_resumes": []
            }

        # 3. Format results for analysis output
        results = []
        for resume in matched_docs:
            score_percentage = round(resume.get("similarity", 0) * 100, 2)
            # Placeholder for feedback - RAG would generate this
            feedback = f"Analysis pending (Score: {score_percentage}%)" # Basic placeholder

            results.append({
                "id": resume.get("id"),
                "filename": resume.get("filename"),
                "file_url": resume.get("file_url"),
                "score_percentage": score_percentage,
                "feedback": feedback # Replace with RAG analysis later
            })

        # Results are already sorted by score descending from the DB function

        return {
            "job_description_preview": job_description[:200] + "..." if len(job_description) > 200 else job_description,
            "analysis_threshold": min_score_threshold,
            "analyzed_resumes": results
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {e}"
        )