from django.conf import settings
from google import genai

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def get_embedding(text: str):
    

    response = client.models.embed_content(
        model="models/gemini-embedding-001",  # stable embedding model
        contents=text
    )

    return response.embeddings[0].values