FROM python:3.12-slim-bookworm

RUN useradd --create-home --uid 10001 harness
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY candidate ./candidate
COPY benchmarks ./benchmarks
RUN pip install --no-cache-dir .
USER harness

ENTRYPOINT ["epic-intel"]
CMD ["benchmark", "--suite", "smoke", "--artifacts", "/artifacts"]
