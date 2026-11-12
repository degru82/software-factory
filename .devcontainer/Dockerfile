FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# uv: 로컬과 같은 버전으로 고정
COPY --from=ghcr.io/astral-sh/uv:0.5.26 /uv /uvx /usr/local/bin/

# cypher-shell: app 컨테이너에서 neo4j 서비스로 접속 확인용 (Java 17 필요)
# base 이미지의 서명되지 않은 yarn 저장소 제거
RUN rm -f /etc/apt/sources.list.d/yarn.list

# 기본 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Neo4j apt 저장소 설정
RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/neotechnology.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/neotechnology.gpg] https://debian.neo4j.com stable 5" \
       > /etc/apt/sources.list.d/neo4j.list

# cypher-shell 설치
RUN apt-get update && apt-get install -y --no-install-recommends cypher-shell \
    && rm -rf /var/lib/apt/lists/*
