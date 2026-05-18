import os
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.services.document_service import DOCUMENT_STORE


class QueryService:
    def retrieve_context(self, question: str, top_k: int = 5):
        all_chunks = []

        for document_id, chunks in DOCUMENT_STORE.items():
            all_chunks.extend(chunks)

        if not all_chunks:
            return "", []

        texts = [chunk["text"] for chunk in all_chunks]

        vectorizer = TfidfVectorizer(stop_words="english")
        vectors = vectorizer.fit_transform(texts + [question])

        similarities = cosine_similarity(vectors[-1], vectors[:-1]).flatten()

        ranked_indexes = similarities.argsort()[::-1][:top_k]

        context = ""
        sources = []

        for index in ranked_indexes:
            chunk = all_chunks[index]
            score = float(similarities[index])

            context += chunk["text"] + "\n\n"

            sources.append(
                {
                    "document_name": chunk["document_name"],
                    "text": chunk["text"][:500],
                    "score": score,
                }
            )

        return context, sources

    def generate_with_huggingface(self, question: str, context: str):
        hf_token = os.getenv("HF_API_TOKEN", "")

        if not hf_token:
            return None

        url = "https://api-inference.huggingface.co/models/google/flan-t5-base"

        headers = {
            "Authorization": f"Bearer {hf_token}"
        }

        prompt = f"""
Answer the question using the document context.

Context:
{context[:3000]}

Question:
{question}

Answer:
"""

        response = requests.post(
            url,
            headers=headers,
            json={
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 250,
                    "temperature": 0.2,
                },
                "options": {
                    "wait_for_model": True
                }
            },
            timeout=120,
        )

        if response.status_code != 200:
            return None

        result = response.json()

        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text")

        return None

    def fallback_answer(self, question: str, context: str):
        sentences = context.replace("\n", " ").split(". ")
        useful = []

        for sentence in sentences:
            clean = sentence.strip()
            if len(clean) > 50:
                useful.append(clean)

            if len(useful) == 7:
                break

        if not useful:
            return "I found the document, but I could not extract enough readable content."

        answer = "Here are the key points from the uploaded document:\n\n"

        for point in useful:
            answer += f"- {point}.\n"

        return answer

    def answer_question(self, question: str):
        context, sources = self.retrieve_context(question)

        if not context.strip():
            return {
                "answer": "Please upload a PDF or TXT file first.",
                "sources": [],
            }

        hf_answer = self.generate_with_huggingface(question, context)

        if hf_answer:
            answer = hf_answer
        else:
            answer = self.fallback_answer(question, context)

        return {
            "answer": answer,
            "sources": sources,
        }
