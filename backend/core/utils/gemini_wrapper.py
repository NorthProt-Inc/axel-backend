from typing import Any, Optional
from google import genai
from google.genai import types
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from backend.core.logging import get_logger

_logger = get_logger("gemini_wrapper")

DEFAULT_TIMEOUT_SECONDS = 120.0

_singleton_wrapper: Optional["GenerativeModelWrapper"] = None
_singleton_lock = None


def get_gemini_wrapper() -> "GenerativeModelWrapper":
    global _singleton_wrapper, _singleton_lock
    import threading
    if _singleton_lock is None:
        _singleton_lock = threading.Lock()
    if _singleton_wrapper is None:
        with _singleton_lock:
            if _singleton_wrapper is None:
                _singleton_wrapper = GenerativeModelWrapper()
    return _singleton_wrapper


class GenerativeModelWrapper:
    """Thin wrapper around google-genai SDK.

    Handles SDK client creation, content normalization, config assembly,
    and response wrapping. Retry/circuit-breaker is the caller's responsibility
    (use utils.retry or llm.clients).
    """

    def __init__(self, client_or_model: Any = None, model_name: str | None = None):
        if isinstance(client_or_model, str):
            model_name = client_or_model
            client_or_model = None

        if client_or_model is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY 환경변수가 필요합니다")
            _logger.info("genai.Client 생성 시작")
            self.client = genai.Client(api_key=api_key)
            _logger.info("genai.Client 생성 완료")
        else:
            self.client = client_or_model

        from backend.config import DEFAULT_GEMINI_MODEL
        self.model_name = model_name or DEFAULT_GEMINI_MODEL

    def clone(self) -> "GenerativeModelWrapper":
        return GenerativeModelWrapper(model_name=self.model_name)

    # ------------------------------------------------------------------
    # Config assembly
    # ------------------------------------------------------------------

    @staticmethod
    def _build_config(
        generation_config: Any,
        enable_thinking: bool,
        thinking_level: str | None,
        tools: Any,
        force_tool_call: bool,
    ) -> types.GenerateContentConfig | None:
        thinking_config = None
        if enable_thinking:
            kwargs: dict[str, Any] = {"include_thoughts": True}
            if thinking_level:
                kwargs["thinking_level"] = thinking_level
            thinking_config = types.ThinkingConfig(**kwargs)

        tool_config = None
        if tools and force_tool_call:
            tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            )

        if not generation_config and not thinking_config and not tools and not tool_config:
            return None

        temperature = None
        max_output_tokens = None
        if generation_config:
            if isinstance(generation_config, types.GenerateContentConfig):
                temperature = generation_config.temperature
                max_output_tokens = generation_config.max_output_tokens
                thinking_config = thinking_config or generation_config.thinking_config
                tools = tools or generation_config.tools
            else:
                temperature = getattr(generation_config, "temperature", None)
                max_output_tokens = getattr(generation_config, "max_output_tokens", None)

        return types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            thinking_config=thinking_config,
            tools=tools,
            tool_config=tool_config,
        )

    # ------------------------------------------------------------------
    # Generate content (single attempt — caller retries if needed)
    # ------------------------------------------------------------------

    def generate_content_sync(
        self,
        contents: Any,
        stream: bool = False,
        generation_config: Any = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        enable_thinking: bool = False,
        thinking_level: str | None = None,
        tools: Any = None,
        force_tool_call: bool = False,
    ) -> "GenerateContentResponseWrapper":
        if isinstance(contents, str):
            contents = [types.Content(role="user", parts=[types.Part.from_text(text=contents)])]
        elif isinstance(contents, list) and contents and isinstance(contents[0], str):
            parts = [types.Part.from_text(text=p) for p in contents]
            contents = [types.Content(role="user", parts=parts)]

        config = self._build_config(
            generation_config, enable_thinking, thinking_level, tools, force_tool_call,
        )

        _logger.info(
            "generate_content_sync 시작",
            model=self.model_name,
            stream=stream,
            timeout=timeout_seconds,
            has_config=config is not None,
        )

        if stream:
            response_stream = self.client.models.generate_content_stream(
                model=self.model_name, contents=contents, config=config,
            )
            return GenerateContentResponseWrapper(response_stream, stream=True)

        def _call_sdk() -> Any:
            return self.client.models.generate_content(
                model=self.model_name, contents=contents, config=config,
            )

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call_sdk)
            try:
                response = future.result(timeout=timeout_seconds)
                return GenerateContentResponseWrapper(response, stream=False)
            except FuturesTimeoutError:
                _logger.warning("Gemini API timeout", timeout_seconds=timeout_seconds)
                raise TimeoutError(f"Gemini API timeout ({timeout_seconds}s)")

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    async def embed_content(
        self,
        model: str,
        contents: Any,
        config: Any = None,
        task_type: str | None = None,
    ) -> Any:
        if config is None and task_type:
            config = {"task_type": task_type}
        return self.client.models.embed_content(
            model=model, contents=contents, config=config,
        )

    def embed_content_sync(
        self,
        model: str,
        contents: Any,
        config: Any = None,
        task_type: str | None = None,
    ) -> Any:
        if config is None and task_type:
            config = {"task_type": task_type}
        return self.client.models.embed_content(
            model=model, contents=contents, config=config,
        )

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    async def generate_images(
        self,
        model: str,
        prompt: str,
        config: Any = None,
    ) -> Any:
        return self.client.models.generate_images(
            model=model, prompt=prompt, config=config,
        )

    def generate_images_sync(
        self,
        model: str,
        prompt: str,
        config: Any = None,
    ) -> Any:
        return self.client.models.generate_images(
            model=model, prompt=prompt, config=config,
        )


# ======================================================================
# Response wrapper
# ======================================================================

class GenerateContentResponseWrapper:

    def __init__(self, response: Any, stream: bool = False):
        self._response = response
        self._stream = stream
        self._text = ""
        self._thought_text = ""
        self._chunks: list[str] = []
        self._is_thought = False

        if not stream:
            if hasattr(response, "candidates") and response.candidates:
                content = response.candidates[0].content
                parts = content.parts if content and hasattr(content, "parts") and content.parts else []
                for part in parts:
                    if hasattr(part, "thought") and part.thought:
                        self._thought_text += part.text if part.text else ""
                    elif part.text:
                        self._text += part.text

                if len(parts) == 1 and hasattr(parts[0], "thought"):
                    self._is_thought = parts[0].thought
            elif hasattr(response, "text"):
                self._text = response.text if response.text else ""

    @property
    def text(self) -> str:
        if self._stream:
            return "".join(self._chunks)
        return self._text

    @property
    def thought(self) -> str:
        return self._thought_text

    @property
    def is_thought(self) -> bool:
        return self._is_thought

    @property
    def function_call(self) -> dict[str, Any] | None:
        """Return the function call if present, or None."""
        return getattr(self, "_function_call", None)

    def __iter__(self):
        if self._stream:
            for chunk in self._response:
                is_thought = False
                text_chunk = ""
                function_calls: list[dict[str, Any]] = []

                try:
                    if hasattr(chunk, "candidates") and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, "content") and candidate.content:
                            parts = candidate.content.parts if hasattr(candidate.content, "parts") else []
                            for part in parts:
                                if hasattr(part, "thought") and part.thought:
                                    is_thought = True
                                if hasattr(part, "text") and part.text:
                                    text_chunk += part.text
                                if hasattr(part, "function_call") and part.function_call:
                                    fc = part.function_call
                                    if fc.name:
                                        function_calls.append({
                                            "name": fc.name,
                                            "args": dict(fc.args) if fc.args else {},
                                        })
                    elif hasattr(chunk, "text") and chunk.text:
                        text_chunk = chunk.text
                except Exception as e:
                    _logger.warning("Chunk parsing error", error=str(e)[:100])
                    continue

                for fc in function_calls:
                    wrapper = GenerateContentResponseWrapper.__new__(GenerateContentResponseWrapper)
                    wrapper._response = chunk
                    wrapper._stream = False
                    wrapper._text = ""
                    wrapper._thought_text = ""
                    wrapper._chunks = []
                    wrapper._is_thought = False
                    wrapper._function_call = fc
                    yield wrapper

                if text_chunk and not function_calls:
                    self._chunks.append(text_chunk)
                    wrapper = GenerateContentResponseWrapper.__new__(GenerateContentResponseWrapper)
                    wrapper._response = chunk
                    wrapper._stream = False
                    wrapper._text = text_chunk
                    wrapper._thought_text = ""
                    wrapper._chunks = []
                    wrapper._is_thought = is_thought
                    wrapper._function_call = None
                    yield wrapper
        else:
            yield self
