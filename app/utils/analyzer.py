from sentence_transformers import SentenceTransformer, util
from typing import Tuple

# Load model once globally
model = SentenceTransformer('all-MiniLM-L6-v2')

def analyze_resume_similarity(resume_text: str, job_desc_text: str) -> Tuple[float, str]:
    """
    Compares a resume and job description, returning a similarity percentage and feedback.
    """
    # Step 1: Generate embeddings
    resume_embedding = model.encode(resume_text, convert_to_tensor=True)
    job_desc_embedding = model.encode(job_desc_text, convert_to_tensor=True)

    # Step 2: Compute cosine similarity
    similarity_score = util.cos_sim(resume_embedding, job_desc_embedding).item()
    percentage_score = round(similarity_score * 100, 2)

    # Step 3: Basic keyword-based feedback
    job_keywords = set(job_desc_text.lower().split())
    resume_keywords = set(resume_text.lower().split())
    missing_keywords = list(job_keywords - resume_keywords)

    if percentage_score >= 80:
        feedback = "✅ Great match! Your resume aligns very well with the job description."
    elif percentage_score >= 60:
        feedback = "⚠️ Decent match. You can improve your resume by adding more relevant content."
    else:
        feedback = "❌ Weak match. Try tailoring your resume more closely to the job description."

    if missing_keywords:
        top_missing = ", ".join(sorted(missing_keywords)[:10])
        feedback += f"\n\n📌 Consider adding these terms to improve alignment: {top_missing}"

    return percentage_score, feedback

