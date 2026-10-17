# Build context: the repo root (docker build -f api/Dockerfile .). The deploy workflow stages the same layout.
FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# CPU-only torch: laya imports it for tensor collation; inference itself runs on onnxruntime
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

FROM python:3.11-slim
RUN useradd --create-home --uid 1000 verdict
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/api:/app/training HF_HOME=/home/verdict/.cache/huggingface \
    TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2
WORKDIR /app
COPY --chown=verdict api/verdict_api api/verdict_api
COPY --chown=verdict training/verdict_train/__init__.py training/verdict_train/checks.py training/verdict_train/scoring.py training/verdict_train/
USER verdict
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/healthz', timeout=4).status==200 else 1)"
CMD ["uvicorn", "verdict_api.app:app_factory", "--factory", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
