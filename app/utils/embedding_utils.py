from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List

# Load the pre-trained model (Choose one and be consistent)
# Option 1: Smaller, faster
# model = SentenceTransformer("all-MiniLM-L6-v2") # Dimension: 384
# Option 2: Generally better performance
model = SentenceTransformer("all-mpnet-base-v2") # Dimension: 768
# Make sure the dimension matches your Supabase vector column and DB function!

# Convert text to vector embedding
def get_embedding(text: str) -> List[float]:
    """
    Generates a vector embedding for the given text.

    Args:
        text: The input string.

    Returns:
        A list of floats representing the embedding vector.
    """
    if not text or not isinstance(text, str):
        # Return a zero vector of the correct dimension if input is invalid
        print("Warning: Received invalid text for embedding. Returning zero vector.")
        return [0.0] * model.get_sentence_embedding_dimension()

    embedding = model.encode(text, convert_to_tensor=False) # Get numpy array
    return embedding.tolist() # Convert to list for JSON serialization / Supabase

# compute_similarity function is removed as similarity is now calculated in Supabase