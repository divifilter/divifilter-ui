# --- Build stage: install dependencies into an isolated prefix ---
FROM python:3.14 AS builder

WORKDIR /build

# Copy only the dependency manifest first so the (expensive) pip install layer is cached and only
# rebuilds when requirements.txt actually changes — not on every source edit.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage: slim image with just the app and its deps ---
# NOTE: runs as root so uvicorn can bind the privileged port 80 (Northflank forwards to container port 80).
# To run non-root later, switch uvicorn to an unprivileged port (e.g. 8080) and set the Northflank port to match.
FROM python:3.14-slim AS runtime

WORKDIR /divifilter

# Bring over the packages installed in the build stage.
COPY --from=builder /install /usr/local

# Copy the application source.
COPY . /divifilter

EXPOSE 80

# curl isn't present on the slim image, so probe /health with the Python stdlib instead.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:80/health').status==200 else 1)" || exit 1

ENTRYPOINT ["uvicorn", "dividend_stocks_filterer.app:app", "--host", "0.0.0.0", "--port", "80", "--workers", "4"]
