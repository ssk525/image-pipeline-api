FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY src ./src
COPY run_api.py .
COPY samples ./samples

ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["python", "run_api.py"]
