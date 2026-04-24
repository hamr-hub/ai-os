FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN sed -i 's@archive.ubuntu.com@mirrors.aliyun.com@g' /etc/apt/sources.list \
    && sed -i 's@security.ubuntu.com@mirrors.aliyun.com@g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3.10-venv \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

WORKDIR /app

COPY requirements.txt .

RUN python3 -m venv .venv && \
    .venv/bin/pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ && \
    .venv/bin/pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY . .

EXPOSE 35000

CMD ["/app/.venv/bin/python", "main.py"]