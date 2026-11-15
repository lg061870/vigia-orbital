# Hugging Face Space (SDK: Docker) for the Vigía Orbital forecast API.
# Builds from the public GitHub repo, so this file (plus README.md) is all the Space needs.
FROM python:3.11-slim
ARG REPO=https://raw.githubusercontent.com/lg061870/vigia-orbital/main
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
RUN set -e; for f in vigia/__init__.py vigia/model.py api/main.py api/requirements.txt \
      data/csv/canton_day.csv data/csv/detection.csv data/results/OFFICIAL_RUN.json \
      data/results/20261115T152753Z/model_params.json data/results/20261115T152753Z/manifest.json; do \
      curl -fsSL --create-dirs -o "$f" "$REPO/$f"; done
RUN pip install --no-cache-dir -r api/requirements.txt
RUN chown -R user /home/user/app
USER user
EXPOSE 7860
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
