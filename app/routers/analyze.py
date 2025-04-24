from fastapi import APIRouter, HTTPException, status, Body
from app.utils.analyzer import analyze_resume_similarity
from app.utils.supabase_utils import get_all_resumes_from_db

router = APIRouter(prefix="/analyze", tags=["Analyze"])

@router.post("/resumes")
async def analyze_all_resumes(job_description: str = Body(..., embed=True)):
    """
    Analyzes all resumes from the database against a job description and returns
    a score and feedback for each.
    """
    try:
        resumes = await get_all_resumes_from_db()
        if not resumes:
            raise HTTPException(status_code=404, detail="No resumes found in database.")

        results = []
        for resume in resumes:
            text = resume.get("text_content", "")
            score, feedback = analyze_resume_similarity(text, job_description)

            results.append({
                "id": resume.get("id"),
                "filename": resume.get("filename"),
                "file_url": resume.get("file_url"),
                "score_percentage": score,
                "feedback": feedback
            })

        results = sorted(results, key=lambda x: x["score_percentage"], reverse=True)

        return {
            "job_description": job_description,
            "analyzed_resumes": results
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {e}"
        )

