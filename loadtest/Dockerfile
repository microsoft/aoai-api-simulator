FROM python@sha256:2098ae1a93b47ea9ea4ea66a6ff4659deb770c45e35244a7a5db73ea4e93d2a5 AS base
WORKDIR /app


COPY ./requirements.txt ./
RUN pip install -r requirements.txt --require-hashes --no-deps

COPY . .

