from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Load the pre-trained model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Convert text to vector
def get_embedding(text: str) -> np.ndarray:
    return model.encode([text])[0]

# Compare JD and Resume
def compute_similarity(jd_embed, resume_embed) -> float:
    return float(cosine_similarity([jd_embed], [resume_embed])[0][0])