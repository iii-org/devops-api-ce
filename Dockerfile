FROM python:3.9.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN echo "1.0.0" > git_tag

COPY . .
RUN git rev-parse HEAD > git_commit
RUN git log -1 --date=iso8601 --format="%ad" > git_date
#ENTRYPOINT ["apis/gunicorn.sh"]
CMD ["python", "apis/api.py"]