# Vigía Orbital forecast API (FastAPI). Live FIRMS data needs: docker run -e FIRMS_MAP_KEY=... 
# Build: docker build -t vigia-api .  Run: docker run -p 8000:8000 vigia-api
FROM python:3.11-slim
WORKDIR /app
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY vigia/ vigia/
COPY api/ api/
COPY data/csv/canton_day.csv data/csv/detection.csv data/csv/
COPY data/results/ data/results/
COPY data/nasa_power_guanacaste_daily_2026.csv data/
COPY site/data/cantons.geojson site/data/
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
