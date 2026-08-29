import httpx

from .config import settings


class OllamaError(RuntimeError):
    pass


async def _post(
    path: str,
    payload: dict,
    timeout: float,
):
    url = settings.ollama_base_url.rstrip("/") + path

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


async def embed(text: str) -> list[float]:
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

    # /api/embed returns a list of vectors.
    # We send one piece of text at a time,
    # so use the first vector.
    vector = (
        embeddings[0]
        if isinstance(embeddings[0], list)
        else embeddings
    )

    return [
        float(value)
        for value in vector
    ]


async def generate(prompt: str) -> str:
    """
    Generate an answer using the configured
    Ollama LLM.
    """

    data = await _post(
        "/api/generate",
        {
            "model": settings.ollama_llm_model,
            "prompt": prompt,
            "stream": False,
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


async def check_ollama() -> dict:
    """
    Check whether Ollama is reachable and whether
    the required models are installed.
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
            "embedding_model_present": embedding_present,
            "llm_model_present": llm_present,
        }

    except httpx.RequestError:
        return {
            "ok": False,
            "error": (
                "Ollama is not reachable at "
                f"{settings.ollama_base_url}"
            ),
        }