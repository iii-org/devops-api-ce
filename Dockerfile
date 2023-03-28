FROM python:3.9.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl && apt clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x sonar-scanner-4.8.0 -R
RUN echo "lite-0.0.7" > git_tag && git rev-parse HEAD > git_commit && git log -1 --date=iso8601 --format="%ad" > git_date
CMD ["python", "apis/api.py"]
