import httpx

from .config import settings


class OllamaError(RuntimeError):
    pass


async def _post(
    path: str,
    payload: dict,
    timeout: float,
):
    """
    Send a POST request to the Ollama API.
    """

    url = (
        settings.ollama_base_url.rstrip("/")
        + path
    )

    try:
        async with httpx.AsyncClient(
            timeout=timeout
        ) as client:

            response = await client.post(
                url,
                json=payload,
            )

    except httpx.RequestError as exc:
        raise OllamaError(
            f"Cannot reach Ollama at "
            f"{settings.ollama_base_url}. "
            "Start Ollama and try again."
        ) from exc

    if response.status_code >= 400:

        detail = response.text[:1000]

        raise OllamaError(
            f"Ollama returned HTTP "
            f"{response.status_code}: {detail}"
        )

    try:
        return response.json()

    except ValueError as exc:
        raise OllamaError(
            "Ollama returned an invalid JSON response."
        ) from exc


# =========================================================
# EMBEDDINGS
# =========================================================

async def embed(
    text: str,
) -> list[float]:
    """
    Generate an embedding for the supplied text
    using the configured Ollama embedding model.
    """

    data = await _post(
        "/api/embed",
        {
            "model": settings.ollama_embed_model,
            "input": text,
        },
        120,
    )

    embeddings = data.get("embeddings")

    if not embeddings or not isinstance(
        embeddings,
        list,
    ):
        raise OllamaError(
            "Ollama did not return an embedding."
        )

    # Ollama /api/embed returns a list of vectors.
    #
    # Since we send one piece of text at a time,
    # use the first vector.

    vector = (
        embeddings[0]
        if isinstance(
            embeddings[0],
            list,
        )
        else embeddings
    )

    return [
        float(value)
        for value in vector
    ]


# =========================================================
# LLM GENERATION
# =========================================================

async def generate(
    prompt: str,
) -> str:
    """
    Generate an answer using the configured
    Ollama language model.
    """

    data = await _post(
        "/api/generate",
        {
            "model": settings.ollama_llm_model,
            "prompt": prompt,
            "stream": False,

            # Low temperature makes responses
            # more deterministic and reduces
            # unnecessary hallucination.

            "options": {
                "temperature": 0.0,
            },
        },
        180,
    )

    answer = data.get("response")

    if not answer:
        raise OllamaError(
            "Ollama returned an empty response."
        )

    return answer.strip()


# =========================================================
# DOCUMENT SUMMARIZATION
# =========================================================

async def summarize(
    text: str,
) -> str:
    """
    Summarize a section of document content.

    This function is used by the hierarchical
    document summarization pipeline.

    The model is instructed to use only the
    supplied document content.
    """

    prompt = f"""
You are an AI document analysis assistant.

Your task is to summarize the supplied document content.

IMPORTANT RULES:

1. Use ONLY the information contained in the
   supplied document content.

2. Do NOT use outside knowledge.

3. Do NOT invent facts.

4. Preserve important information such as:
   - requirements
   - features
   - user roles
   - dates
   - numbers
   - technical details
   - constraints
   - important facts

5. Remove unnecessary repetition.

6. Keep the summary concise but informative.

DOCUMENT CONTENT:

{text}

DOCUMENT SUMMARY:
"""

    return await generate(prompt)


# =========================================================
# OLLAMA HEALTH CHECK
# =========================================================

async def check_ollama() -> dict:
    """
    Check whether Ollama is reachable and whether
    the configured embedding and LLM models are
    installed.
    """

    url = (
        settings.ollama_base_url.rstrip("/")
        + "/api/tags"
    )

    try:

        async with httpx.AsyncClient(
            timeout=5
        ) as client:

            response = await client.get(url)

        if response.status_code >= 400:

            return {
                "ok": False,
                "error": response.text[:500],
            }

        models = response.json().get(
            "models",
            [],
        )

        names = [
            model.get("name", "")
            for model in models
        ]

        embedding_present = any(
            settings.ollama_embed_model in name
            for name in names
        )

        llm_present = any(
            settings.ollama_llm_model in name
            for name in names
        )

        return {
            "ok": True,
            "models": names,
            "embedding_model_present": (
                embedding_present
            ),
            "llm_model_present": (
                llm_present
            ),
        }

    except httpx.RequestError:

        return {
            "ok": False,
            "error": (
                "Ollama is not reachable at "
                f"{settings.ollama_base_url}"
            ),
        }