from fastapi import APIRouter, HTTPException
from app.utils.supabase_utils import get_all_resumes_from_db
from app.utils.embedding_utils import get_embedding, compute_similarity

router = APIRouter(prefix="/match", tags=["Matching"])

@router.post("/jd")
async def match_resumes_with_jd(jd: str):
    try:
        jd_embedding = get_embedding(jd)
        resumes = await get_all_resumes_from_db()
        if not resumes:
            raise HTTPException(status_code=404, detail="No resumes found.")

        matches = []
        for resume in resumes:
            text = resume.get("text_content", "")
            resume_embedding = get_embedding(text)
            score = compute_similarity(jd_embedding, resume_embedding)
            matches.append({
                "id": resume.get("id"),
                "filename": resume.get("filename"),
                "file_url": resume.get("file_url"),
                "score": round(score * 100, 2)
            })

        matches = sorted(matches, key=lambda x: x["score"], reverse=True)
        return {"job_description": jd, "matched_resumes": matches}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
