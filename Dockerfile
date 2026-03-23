FROM python:3.12-slim

WORKDIR /app

# Install ChromaDB + httpx for vector memory
RUN pip install --no-cache-dir chromadb httpx

COPY proxy.py summarizer.py skill_engine.py rag_memory.py embedding_provider.py cost_tracker.py virtual_keys.py providers.json ./
RUN mkdir -p /app/data/conversations /app/data/chroma_db

ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

EXPOSE 8900

CMD ["python", "proxy.py"]
