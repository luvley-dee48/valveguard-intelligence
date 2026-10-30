FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY frontend ./frontend
RUN useradd -m nexora && mkdir -p /data && chown nexora /data
USER nexora
# Mount a volume at /data so the database survives restarts.
ENV DATABASE_URL=sqlite:////data/nexora.db
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
