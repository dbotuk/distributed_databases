FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web_counter/api/web_counter.py .

EXPOSE 8080

ENV HOST=0.0.0.0
ENV PORT=8080

# Timeout keep-alive 120s so connections aren't closed while the single worker is busy on Hazelcast.
CMD ["sh", "-c", "uvicorn web_counter:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080} --workers ${WORKERS:-1} --timeout-keep-alive 120"]

