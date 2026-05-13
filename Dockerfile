# GBFS Audit Catalogue -- bit-exact reproduction image.
#
# Build:
#   docker build -t gbfs-audit:1.0 .
#
# Run the Streamlit dashboard:
#   docker run --rm -p 8501:8501 gbfs-audit:1.0 \
#       streamlit run app/streamlit_app.py --server.port=8501 --server.headless=true
#
# Run a one-off Python call:
#   docker run --rm gbfs-audit:1.0 \
#       python -c "from audit_pipeline import load_catalogue; print(load_catalogue().shape)"

FROM python:3.11-slim

LABEL org.opencontainers.image.title="GBFS Audit Catalogue"
LABEL org.opencontainers.image.description="Reproducible audit of 1,509 GBFS bike-sharing feeds."
LABEL org.opencontainers.image.source="https://github.com/rohanfosse/gbfs-audit-catalogue"
LABEL org.opencontainers.image.licenses="MIT (code) / ODbL-1.0 (data)"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/gbfs-audit

# Install dependencies first for layer-cache friendliness.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project.
COPY audit_pipeline ./audit_pipeline
COPY app ./app
COPY notebooks ./notebooks
COPY catalogue ./catalogue
COPY README.md LICENSE LICENSE-DATA CITATION.cff ./

EXPOSE 8501
CMD ["python", "-c", "from audit_pipeline import load_catalogue; print(load_catalogue().shape)"]
