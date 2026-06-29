FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/

# The MCP server listens on this port (overridable via PORT env var).
EXPOSE 8000

CMD ["python", "server/main.py"]
