FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 10001 app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app . .

USER 10001
EXPOSE 8000

# One gunicorn process per container, with threads. Scaling is done with more
# replicas, which keeps the Prometheus metrics of each process scrapeable.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", "--threads", "8", "--worker-class", "gthread", \
     "--access-logfile", "-", "--timeout", "30"]
