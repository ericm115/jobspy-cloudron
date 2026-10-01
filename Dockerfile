FROM cloudron/python-base:3.12-20260920@sha256:49c5a00c1110ec76cb5122e48c26dbc26a1c04e020c9ee230be95272c66eb86b

RUN python3 -m venv /app/code/venv && /app/code/venv/bin/pip install --no-cache-dir python-jobspy==1.1.82
COPY app.py start.sh /app/code/
ENV PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
EXPOSE 8000
CMD ["/bin/bash", "/app/code/start.sh"]
