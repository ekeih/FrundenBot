FROM python:3.10-alpine

WORKDIR /app
RUN apk add --update --no-cache build-base libffi-dev openssl-dev

COPY README.md requirements.txt setup.py ./
COPY frundenbot frundenbot
RUN pip install .

USER nobody
CMD ["frundenbot"]
