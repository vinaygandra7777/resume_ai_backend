from fastapi import APIRouter, HTTPException, status, Body
from app.utils.supabase_utils import search_resumes_by_vector
from app.utils.embedding_utils import get_embedding
import logging
from typing import Dict, Any, List, Optional
import os
from dotenv import load_dotenv

# LangChain imports for RAG
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.llms import HuggingFaceHub
from langchain_core.output_parsers import StrOutputParser

load_dotenv() # Ensure env vars are loaded

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["Analyze"])

# --- RAG Model Setup ---
HF_API_KEY = os.getenv("HUGGING_FACE_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "TinyLlama/TinyLlama-1.1B-Chat-v1.0") # Configurable model

if not HF_API_KEY:
    # Log a critical error but allow the app to start.
    # Endpoints that use the LLM will raise an HTTPException if called.
    logger.critical("HUGGING_FACE_API_KEY is not set. RAG analysis endpoints will not function.")
    llm = None # Indicate that LLM is not available
else:
    try:
        logger.info(f"Initializing LLM: {LLM_MODEL_NAME}")
        # Using HuggingFaceHub for hosted models
        # Ensure the model is suitable for instruction following
        llm = HuggingFaceHub(
            repo_id=LLM_MODEL_NAME,
            huggingfacehub_api_token=HF_API_KEY,
            task="text-generation", # Use text-generation for Mistral instruct
             # Adjust generation parameters if needed
            model_kwargs={
                "max_new_tokens": 512, # Max tokens for the feedback
                "temperature": 0.7, # Control randomness
                "top_k": 50,
                "do_sample": True,
                "eos_token_id": 2 # Example: EOS token for Mistral - check model details if needed
            }
        )
        logger.info("LLM initialized successfully.")

        # Define the RAG Prompt Template
        rag_prompt = ChatPromptTemplate.from_template("""<|user|>You are an AI assistant specialized in analyzing resumes against job descriptions.
        Given the resume text and a job description, provide specific, actionable feedback on how the resume can be improved to better match the job requirements.

        Focus areas for feedback:
        - Missing keywords, skills, or qualifications mentioned in the job description that are not present or not clearly highlighted in the resume.
        - Sections in the resume (summary, experience, skills) that could be tailored to better align with the specific role described in the job description.
        - Suggestions for rephrasing bullet points in the experience section to emphasize achievements or responsibilities relevant to the job description, perhaps using STAR method if applicable.
        - Pointing out job description requirements that seem unmet or require more emphasis in the resume.

        Format the feedback clearly, using bullet points or a numbered list for suggestions.
        Ensure the feedback is constructive, polite, and easy for the job seeker to understand and implement.
        Only base feedback on the provided resume text and job description. Do not invent qualifications or experience.
        Start the feedback directly, without introductory sentences like "Here is the feedback" or "Based on your analysis...".

        Resume Text:
        {resume_text}

        Job Description:
        {job_description}

        Constructive Feedback for Resume Improvement:
        """)

        # Create the LangChain chain
        # We use a simple chain because we retrieve the full document text via Supabase RPC first
        # The LLM processes the JD and the *full* retrieved resume text directly via the prompt
        rag_chain = rag_prompt | llm | StrOutputParser()
        logger.info("RAG chain created.")

    except Exception as e:
        logger.critical(f"Failed to initialize LLM or RAG chain: {e}", exc_info=True)
        llm = None # Explicitly set llm to None on failure
        rag_chain = None

@router.post("/resumes")
async def analyze_top_resumes(
    job_description: str = Body(..., embed=True, description="The full text of the job description."),
    min_score_threshold: float = Body(0.5, embed=True, description="Minimum similarity score (0.0 to 1.0) to include in analysis."),
    max_results: int = Body(10, embed=True, description="Maximum number of resumes to retrieve and analyze.") # Default changed to 10 for analysis scope
    ) -> Dict[str, Any]:
    """
    Retrieves top N resumes matching a job description using vector similarity,
    calculates an ATS-like score (similarity percentage), and generates
    AI-powered feedback for each using RAG.

    Requires the Supabase 'match_resumes' DB function to return `text_content`
    and the Hugging Face API key to be set up for RAG feedback.
    """
    if not job_description:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job description cannot be empty.")
    if not (0.0 <= min_score_threshold <= 1.0):
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Minimum score threshold must be between 0.0 and 1.0.")
    if max_results <= 0:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Max results must be positive.")

    # Check if LLM is initialized before proceeding to RAG
    if llm is None or rag_chain is None:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail="AI analysis service is not available due to LLM initialization failure. Check server logs."
         )


    try:
        logger.info(f"Analyzing resumes against JD (length: {len(job_description)}). Threshold: {min_score_threshold}, Max Results: {max_results}")

        # 1. Generate embedding for the job description
        jd_embedding = get_embedding(job_description)
        logger.info("JD embedding generated.")

        # 2. Call Supabase function to find similar resumes
        # This call *must* return the 'text_content' column
        matched_docs = await search_resumes_by_vector(
            jd_embedding=jd_embedding,
            match_threshold=min_score_threshold,
            match_count=max_results
        )
        logger.info(f"Retrieved {len(matched_docs)} resumes for analysis based on vector search.")

        if not matched_docs:
             return {
                "job_description_preview": job_description[:200] + "..." if len(job_description) > 200 else job_description,
                "analysis_threshold": min_score_threshold,
                "max_results_requested": max_results,
                "analyzed_resumes": []
            }

        # 3. Generate Feedback for each matched resume using RAG
        results = []
        for i, resume in enumerate(matched_docs):
            resume_id = resume.get("id")
            filename = resume.get("filename")
            file_url = resume.get("file_url")
            # Ensure text_content is available - Supabase RPC MUST return it
            resume_text = resume.get("text_content")
            score_percentage = round(resume.get("similarity", 0) * 100, 2)

            logger.info(f"Processing resume {i+1}/{len(matched_docs)}: {filename} (ID: {resume_id}, Score: {score_percentage}%)")

            feedback = "Could not generate feedback (Text content missing or empty)." # Default feedback
            if resume_text and resume_text.strip():
                try:
                    # --- Call the RAG Chain ---
                    logger.debug(f"Generating feedback for {filename}...")
                    # Pass JD and resume text to the chain based on the prompt template
                    ai_feedback = rag_chain.invoke({
                        "resume_text": resume_text,
                        "job_description": job_description
                    })
                    feedback = ai_feedback.split("Constructive Feedback for Resume Improvement:")[-1].strip()

                    # Remove any remaining template artifacts
                    feedback = feedback.split("Resume Text:")[0].strip()
                    feedback = feedback.split("Job Description:")[0].strip()
                    # Clean up leading/trailing whitespace
                    logger.debug(f"Feedback generated for {filename}.")
                except Exception as rag_e:
                    logger.error(f"Error generating feedback for resume {filename} (ID: {resume_id}): {rag_e}", exc_info=True)
                    feedback = f"Error generating feedback: {rag_e}"
            else:
                 logger.warning(f"Skipping feedback generation for {filename} (ID: {resume_id}) due to empty or missing text content.")


            results.append({
                "id": resume_id,
                "filename": filename,
                "file_url": file_url,
                "ats_score_percentage": score_percentage, # Renamed score for clarity
                "feedback": feedback # This now contains generated feedback
            })

        # Results are already sorted by score descending from the DB function
        # If you need specific sorting after processing, do it here:
        # results.sort(key=lambda x: x["ats_score_percentage"], reverse=True)


        return {
            "job_description_preview": job_description[:200] + "..." if len(job_description) > 200 else job_description,
            "analysis_threshold": min_score_threshold,
            "max_results_requested": max_results,
            "num_results_returned": len(results),
            "analyzed_resumes": results
        }

    except HTTPException as he:
        # Re-raise validation errors or service unavailable errors
        raise he
    except Exception as e:
        logger.error(f"Analysis process failed: {e}", exc_info=True)
        # Catch potential errors from get_embedding, search_resumes_by_vector, etc.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during analysis: {e}"
        )

# Note: The original analyze_all_resumes function is replaced by analyze_top_resumes
# as analyzing *all* resumes for RAG feedback would be prohibitively expensive/slow.
# Analyzing the top N matches is the practical approach.