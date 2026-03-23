FROM python:3.12-slim

WORKDIR /app
COPY proxy.py summarizer.py skill_engine.py rag_memory.py providers.json ./
RUN mkdir -p /app/data/conversations

ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

EXPOSE 8900

CMD ["python", "proxy.py"]
