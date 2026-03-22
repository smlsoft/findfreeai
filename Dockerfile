FROM python:3.12-slim

WORKDIR /app
COPY app.py proxy.py summarizer.py skill_engine.py rag_memory.py claude_brain.py ./
RUN mkdir -p /app/data/conversations

ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

EXPOSE 8899 8900

CMD ["sh", "-c", "python app.py & python proxy.py & wait"]
