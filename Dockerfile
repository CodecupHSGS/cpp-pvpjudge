FROM ubuntu:latest

WORKDIR /usr/src/app

COPY ./requirements.txt .

RUN apt update
RUN apt install python3 python3-pip -y
RUN pip install --no-cache-dir -r requirements.txt

COPY ./files ./files
COPY ./judges/scaffold ./judges/scaffold
COPY ./server ./server

ARG APP_PORT=9000
ARG JUDGE_COUNT=10

EXPOSE ${APP_PORT}

ENV JUDGE_COUNT=${JUDGE_COUNT}
ENV APP_PORT=${APP_PORT}

CMD ["gunicorn", "server.app:app", "-b", "0.0.0.0:9000", "--log-level", "'debug'"]
