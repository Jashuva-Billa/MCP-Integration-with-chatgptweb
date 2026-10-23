FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=10000 \
    MCP_DEPLOYMENT_MODE=cloud \
    MCP_AUTH_ENABLED=true \
    MCP_PERMISSION_PROFILE=safe \
    REPOSITORIES_CONFIG_PATH=/tmp/mcp-runtime/repositories.json \
    MCP_WORKSPACE_ROOT=/tmp/mcp-workspaces

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 mcpuser \
    && mkdir -p /tmp/mcp-runtime /tmp/mcp-workspaces /app/runtime \
    && chown -R mcpuser:mcpuser /tmp/mcp-runtime /tmp/mcp-workspaces /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mcpuser:mcpuser . .

EXPOSE 10000

USER mcpuser

CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-10000}"]
