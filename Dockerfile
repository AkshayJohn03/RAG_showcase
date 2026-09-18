FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY scripts/ scripts/
COPY data/01_raw/ data/01_raw/
COPY data/eval/golden_qa.json data/eval/golden_qa.json
COPY data/eval/baseline.json data/eval/baseline.json

# bake the index so the first boot is warm (re-run after doc changes)
RUN python scripts/ingest.py --strategy parent_child

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
