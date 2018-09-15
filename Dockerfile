FROM python:3.6

ENV PYTHONUNBUFFERED 1

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends

RUN mkdir /booru_qqbot
WORKDIR /booru_qqbot
ADD . /booru_qqbot

RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONPATH="/booru_qqbot/:$PYTHONPATH"