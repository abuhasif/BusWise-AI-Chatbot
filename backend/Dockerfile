# Buswise Python API. Build from the repository root:
#   docker build -f backend/Dockerfile -t buswise-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BUSWISE_HOST=0.0.0.0 \
    PORT=8765

WORKDIR /srv
# Only the runtime code and the read-only database. Tests, the importer and the
# evaluation scripts stay out of the image. server.py uses only the standard library.
# Files are owned by root and read-only, so the app user cannot modify them.
COPY backend/server.py backend/onemap.py backend/
COPY data/bus.db data/bus.db

# Directories 755 and files 644: readable by everyone, writable only by root.
RUN find /srv -type d -exec chmod 755 {} + \
 && find /srv -type f -exec chmod 644 {} + \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin buswise
USER buswise

EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import os,sys,urllib.request as u; sys.exit(0 if u.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health',timeout=2).status==200 else 1)"
CMD ["python", "backend/server.py"]
