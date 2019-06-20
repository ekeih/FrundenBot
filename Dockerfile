FROM python:3.6-alpine

WORKDIR /app
RUN apk add --update --no-cache build-base libffi-dev openssl-dev

RUN mkdir /app/logs && chown nobody /app/logs
COPY requirements.txt requirements.txt
COPY main.py main.py
RUN pip3 install -r requirements.txt

USER nobody
CMD ["python3", "main.py"]
