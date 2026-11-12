FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# uv: 로컬과 같은 버전으로 고정
COPY --from=ghcr.io/astral-sh/uv:0.5.26 /uv /uvx /usr/local/bin/

# cypher-shell: app 컨테이너에서 neo4j 서비스로 접속 확인용 (Java 17 필요)
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg openjdk-17-jre-headless \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/neotechnology.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/neotechnology.gpg] https://debian.neo4j.com stable 5" \
       > /etc/apt/sources.list.d/neo4j.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends cypher-shell \
    && rm -rf /var/lib/apt/lists/*
