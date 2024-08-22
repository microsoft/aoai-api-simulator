FROM python:3.12.1-slim-bullseye AS base
WORKDIR /app


COPY ./requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

