FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN addgroup --system skillshelf && adduser --system --ingroup skillshelf skillshelf
WORKDIR /app
COPY sdk/python /app/sdk/python
RUN python -m pip install --no-cache-dir "/app/sdk/python[web]"
USER skillshelf
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "skillshelf_agents.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
