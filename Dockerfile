FROM python:3.12-slim

WORKDIR /app

# Install Pixlet v0.34.0 for linux amd64 (do not use darwin).
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends curl ca-certificates tar; \
    rm -rf /var/lib/apt/lists/*; \
    curl -fsSL -o /tmp/pixlet.tgz "https://github.com/tidbyt/pixlet/releases/download/v0.34.0/pixlet_0.34.0_linux_amd64.tar.gz"; \
    tar -xzf /tmp/pixlet.tgz -C /usr/local/bin pixlet; \
    chmod +x /usr/local/bin/pixlet; \
    /usr/local/bin/pixlet --version; \
    rm -f /tmp/pixlet.tgz

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Secrets (TIDBYT_*) come from the environment. Mount config.yaml and the OAuth
# dir at runtime, e.g.:
#   docker run --env-file ./secrets.env \
#     -v $PWD/config.yaml:/app/config.yaml \
#     -v ~/.tidbyt/calendar:/root/.tidbyt/calendar \
#     -p 8080:8080 tidbyt-calendar
CMD ["python", "-u", "-m", "tidbyt_calendar"]
