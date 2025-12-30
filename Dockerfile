FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir ".[vault,cache]"
CMD ["python", "-m", "dragonscales"]
