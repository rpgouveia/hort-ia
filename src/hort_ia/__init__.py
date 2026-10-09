def main() -> None:
    """Start the Hort.IA API server (entry point: `uv run hort-ia`)."""
    import uvicorn

    uvicorn.run("hort_ia.api.main:app", host="0.0.0.0", port=8080)
