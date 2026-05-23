from typing import Optional

from app.guardrails import guardrails
from app.llm_providers import get_provider
from app.models import Citation, QueryResponse
from app.vector_store import vector_store
from config import config


class RAGEngine:
    def __init__(self):
        self.provider = get_provider()

    async def get_answer(self, question: str, domain: str = None, language: str = "English") -> QueryResponse:
        if guardrails.check_emergency(question):
            answer = (
                "This sounds like a possible emergency. Call your local emergency services immediately "
                "(for example 911 in the United States) or go to the nearest emergency department. "
                "Do not rely on this app for urgent care."
            )
            if language.lower() != "english":
                answer = self.provider.translate_text(answer, language)
            return QueryResponse(
                answer=answer,
                citations=[],
                confidence=1.0,
                message="Emergency query detected.",
                guardrail_status="emergency",
                language=language,
                search_query=question,
            )

        is_valid, reason = guardrails.validate_input(question)
        if not is_valid:
            return QueryResponse(
                answer=reason,
                citations=[],
                confidence=0.0,
                message=reason,
                guardrail_status="blocked",
                language=language,
                search_query=question,
            )

        search_query = self._normalize_search_query(question, language)
        looks_medical = (
            guardrails.looks_medical_question(question)
            or guardrails.looks_medical_question(search_query)
        )
        search_results = vector_store.query(search_query, n_results=config.TOP_K, domain_filter=domain)
        contexts = search_results.get("documents", [[]])[0]
        metadatas = search_results.get("metadatas", [[]])[0]
        scores = search_results.get("distances", [[]])[0]

        if not contexts:
            if not looks_medical:
                return self._build_unrelated_response(language, search_query)
            return self._build_no_relevant_data_response(language, search_query)

        if not looks_medical and not guardrails.query_matches_context(search_query, contexts):
            return self._build_unrelated_response(language, search_query)

        if looks_medical and not guardrails.query_matches_context(search_query, contexts):
            return self._build_no_relevant_data_response(language, search_query)

        final_citations = self._build_citations(contexts, metadatas, scores)
        if not guardrails.retrieval_supported(scores, config.MIN_RETRIEVAL_SCORE):
            if not looks_medical:
                return self._build_unrelated_response(language, search_query)
            return self._build_no_relevant_data_response(language, search_query, final_citations)

        context_blocks = [
            f"--- Context {index + 1} ---\nScore: {scores[index]:.2f}\n{contexts[index]}"
            for index in range(min(len(contexts), config.MAX_CONTEXTS))
        ]
        context_str = "\n\n".join(context_blocks)

        system_prompt = (
            "You are MediReference AI, a medical RAG assistant for training and education. "
            "Answer only from the supplied context. "
            "If the context is incomplete, say so clearly. "
            "Do not diagnose, prescribe, or provide personalized medical advice. "
            "Use short headings and bullet points. "
            f"Respond in {language}."
        )

        user_prompt = f"""
Original question: {question}
Search query used for retrieval: {search_query}

Guardrail note: {guardrails.build_guardrail_note(question)}

Context:
{context_str}

Write a concise answer with these sections when relevant:
- Summary
- Key Details
- Safety Notes

Mention the relevant source organizations or dataset names when they are present in the context.
"""

        answer_text = self.provider.generate_text(user_prompt, system_prompt=system_prompt)
        if "API key not configured" in answer_text:
            return QueryResponse(
                answer=answer_text,
                citations=final_citations,
                confidence=0.0,
                message="Configuration issue detected.",
                guardrail_status="provider_error",
                language=language,
                search_query=search_query,
            )

        confidence = guardrails.calculate_confidence(scores, answer_text, context_str)
        return QueryResponse(
            answer=answer_text,
            citations=final_citations,
            confidence=confidence,
            guardrail_status="grounded",
            language=language,
            search_query=search_query,
        )

    def _normalize_search_query(self, question: str, language: str) -> str:
        needs_normalization = language.lower() != "english" or any(ord(char) > 127 for char in question)
        if not needs_normalization:
            return question

        result = self.provider.generate_json(
            f"""
Normalize this medical user question into a concise English retrieval query.
Preserve medicine names, diseases, dosages, and lab markers.
Return JSON with the key "english_query".

Question:
{question}
""",
            system_prompt="You translate multilingual medical questions into concise English search queries without adding facts.",
        )
        english_query = result.get("english_query")
        return english_query.strip() if isinstance(english_query, str) and english_query.strip() else question

    def _build_unrelated_response(self, language: str, search_query: str) -> QueryResponse:
        answer = "This topic looks unrelated to the app's medical scope. Please ask a medical, medication, prescription, or lab-related question."
        if language.lower() != "english":
            answer = self.provider.translate_text(answer, language)

        return QueryResponse(
            answer=answer,
            citations=[],
            confidence=0.0,
            message="Unrelated topic.",
            guardrail_status="unrelated",
            language=language,
            search_query=search_query,
        )

    def _build_no_relevant_data_response(self, language: str, search_query: str, citations=None) -> QueryResponse:
        answer = "No relevant data was found in the current medical library for this question."
        if language.lower() != "english":
            answer = self.provider.translate_text(answer, language)

        return QueryResponse(
            answer=answer,
            citations=citations or [],
            confidence=0.0,
            message="No relevant data found.",
            guardrail_status="no_relevant_data",
            language=language,
            search_query=search_query,
        )

    def _build_citations(self, contexts, metadatas, scores):
        unique_citations = {}
        for index, meta in enumerate(metadatas):
            citation_key = f"{meta['source']}_{meta['title']}"
            chunk_text = contexts[index] if index < len(contexts) else ""
            score = float(scores[index]) if index < len(scores) else None

            if citation_key not in unique_citations:
                unique_citations[citation_key] = {
                    "source": meta["source"],
                    "title": meta["title"],
                    "category": meta["category"],
                    "domain": meta["domain"],
                    "content": chunk_text,
                    "last_updated": meta.get("last_updated"),
                    "score": score,
                }
            else:
                unique_citations[citation_key]["content"] += f"\n\n{chunk_text}"
                if score is not None:
                    existing_score = unique_citations[citation_key].get("score") or score
                    unique_citations[citation_key]["score"] = max(existing_score, score)

        return [Citation(**citation) for citation in unique_citations.values()]


rag_engine = RAGEngine()
