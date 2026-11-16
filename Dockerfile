FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UPGRADEGUARD_REQUIRE_TOKEN=1 UPGRADEGUARD_HTTPS=1
RUN useradd --create-home --uid 10001 guard
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==27.0.1
COPY upgradeguard upgradeguard
COPY contracts contracts
COPY web web
COPY policies policies
COPY examples examples
RUN mkdir -p data evidence work logs && chown -R guard:guard data evidence work logs
USER guard
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "120", "web.app:app"]
