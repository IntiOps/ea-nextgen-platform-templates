# The service image. CI builds it ONCE (operations/package_image.py) with PYTHON_IMAGE pinned to the
# digest of the base it pulled, and CD promotes those exact bytes; nothing builds it per environment.
# Local build from this directory: docker build -t service . (revision then reports "development").
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so a code-only change reuses this layer locally.
COPY app/requirements.txt ./requirements.txt
RUN python -m pip install --no-compile -r requirements.txt \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

# Application code (and build-info.json, which CI writes into the build context) owned by root,
# read-only for the runtime user.
COPY app/ ./

USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
