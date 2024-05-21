FROM python:3.10.14-slim AS python_base

FROM bitnami/git:latest AS buildler

WORKDIR /app

COPY . .

RUN rm -rf /app/iiidevops

RUN git rev-parse HEAD > git_commit && \
    git log -1 --date=iso8601 --format="%ad" > git_date && \
    rm -rf .git

FROM python_base AS library

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN apt-get update && \
    # pip install --upgrade pip && \
    apt-get install --yes --no-install-recommends git && \
    pip install --no-cache-dir -r requirements.txt 
   
FROM python_base AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends git docker.io && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

COPY docker-entrypoint.sh /

# Pull the library
COPY --from=library /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN echo "ce-0.7.1" > git_tag
COPY --from=buildler /app/git_commit .
COPY --from=buildler /app/git_date .
COPY --from=buildler /app .

# ENTRYPOINT ["apis/docker-entrypoint.sh"]
ENTRYPOINT ["/docker-entrypoint.sh"]
