FROM python:3.9.17-slim
RUN apt-get update && apt-get install -y --no-install-recommends git docker.io && apt clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN rm -rf /app/iiidevops
RUN chmod +x sonar-scanner-4.8.0 -R
RUN echo "ce-0.2.1" > git_tag && git rev-parse HEAD > git_commit && git log -1 --date=iso8601 --format="%ad" > git_date
# CMD ["python", "apis/api.py"]
ENTRYPOINT ["/docker-entrypoint.sh"]
