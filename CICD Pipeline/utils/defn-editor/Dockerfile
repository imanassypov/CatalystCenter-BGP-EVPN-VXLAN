FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appuser \
    && useradd -r -m -d /app -g appuser -s /usr/sbin/nologin appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1
ENV HOME=/app
ENV DEFN_PROJECT_ROOT=/data/templates

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health')"

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--pid", "/tmp/gunicorn.pid", "wsgi:app"]
