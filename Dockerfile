# Cloud Run image for the Outreach Operations Agent.
#
# The agent needs BOTH runtimes at execution time:
#   • Python — to run the ADK agent.
#   • Node   — because the MongoDB MCP server is launched via `npx`.
#
# We start from the slim Python image and add Node.js on top.

FROM python:3.12-slim

# Install Node.js 20 (provides node + npx) and curl for the NodeSource setup.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application.
COPY . .

# Cloud Run provides $PORT (defaults to 8080). Serve the agent's web UI.
ENV PORT=8080
EXPOSE 8080

# `adk web` discovers the `outreach_agent` package (which exposes root_agent).
CMD ["sh", "-c", "adk web --host 0.0.0.0 --port ${PORT}"]
