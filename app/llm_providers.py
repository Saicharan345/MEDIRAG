import abc
import base64
import json
from typing import Any, Dict, Optional

import httpx
from groq import Groq

from config import config


class LLMProvider(abc.ABC):
    @abc.abstractmethod
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def analyze_image(self, image_bytes: bytes, mime_type: str, prompt: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def supports_vision(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def translate_text(self, text: str, target_language: str) -> str:
        raise NotImplementedError


class GroqProvider(LLMProvider):
    def __init__(self):
        self.client = Groq(api_key=config.GROQ_API_KEY) if config.GROQ_API_KEY else None

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.client:
            return "Groq API key not configured. Please add GROQ_API_KEY to your .env file."

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        completion = self.client.chat.completions.create(
            model=config.GROQ_TEXT_MODEL,
            messages=messages,
            temperature=0.2,
            max_completion_tokens=900,
        )
        return completion.choices[0].message.content or ""

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        if not self.client:
            return {"error": "Groq API key not configured. Please add GROQ_API_KEY to your .env file."}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        completion = self.client.chat.completions.create(
            model=config.GROQ_TEXT_MODEL,
            messages=messages,
            temperature=0.1,
            max_completion_tokens=800,
            response_format={"type": "json_object"},
        )

        content = completion.choices[0].message.content or "{}"
        return self._safe_json_loads(content)

    def analyze_image(self, image_bytes: bytes, mime_type: str, prompt: str) -> Dict[str, Any]:
        if not self.client:
            return {"error": "Groq API key not configured. Please add GROQ_API_KEY to your .env file."}

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        completion = self.client.chat.completions.create(
            model=config.GROQ_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.1,
            max_completion_tokens=1200,
            response_format={"type": "json_object"},
        )

        content = completion.choices[0].message.content or "{}"
        return self._safe_json_loads(content)

    def supports_vision(self) -> bool:
        return True

    def translate_text(self, text: str, target_language: str) -> str:
        if not text or target_language.lower() == "english":
            return text

        prompt = (
            f"Translate the following medical educational text into {target_language}. "
            "Preserve medicine names, numbers, units, bullet structure, and section headings when possible. "
            "Do not add extra facts.\n\n"
            f"Text:\n{text}"
        )
        return self.generate_text(
            prompt,
            system_prompt="You are a precise medical translator. Translate faithfully and do not add information.",
        )

    def _safe_json_loads(self, payload: str) -> Dict[str, Any]:
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            start = payload.find("{")
            end = payload.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(payload[start:end + 1])
                except json.JSONDecodeError:
                    pass
            return {"error": "The model returned invalid JSON.", "raw_output": payload}


class OllamaProvider(LLMProvider):
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        try:
            response = httpx.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL,
                    "prompt": self._compose_prompt(prompt, system_prompt),
                    "stream": False,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json().get("response", "Error: No response field in Ollama output.")
        except Exception as exc:
            return f"Ollama error: {exc}. Ensure Ollama is running at {config.OLLAMA_BASE_URL}"

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        text = self.generate_text(f"{prompt}\n\nReturn valid JSON only.", system_prompt=system_prompt)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": "Ollama returned invalid JSON.", "raw_output": text}

    def analyze_image(self, image_bytes: bytes, mime_type: str, prompt: str) -> Dict[str, Any]:
        return {"error": "The configured provider does not support image analysis. Please use Groq for prescription images."}

    def supports_vision(self) -> bool:
        return False

    def translate_text(self, text: str, target_language: str) -> str:
        if not text or target_language.lower() == "english":
            return text
        return self.generate_text(
            f"Translate this text to {target_language} without adding information:\n\n{text}",
            system_prompt="You are a precise translator.",
        )

    def _compose_prompt(self, prompt: str, system_prompt: Optional[str]) -> str:
        if not system_prompt:
            return prompt
        return f"{system_prompt}\n\n{prompt}"


def get_provider() -> LLMProvider:
    provider_name = config.LLM_PROVIDER.lower()
    if provider_name == "ollama":
        return OllamaProvider()
    return GroqProvider()
