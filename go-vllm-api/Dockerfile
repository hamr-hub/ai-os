FROM ubuntu:22.04 AS builder

RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list \
    && sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    gcc musl-dev libc6-dev git ca-certificates wget \
    && rm -rf /var/lib/apt/lists/*

ENV GOPROXY=https://goproxy.cn,direct

RUN wget -q https://golang.google.cn/dl/go1.21.13.linux-amd64.tar.gz \
    && rm -rf /usr/local/go \
    && tar -C /usr/local -xzf go1.21.13.linux-amd64.tar.gz \
    && rm go1.21.13.linux-amd64.tar.gz
ENV PATH="/usr/local/go/bin:${PATH}"

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=1 GOOS=linux go build -ldflags="-s -w" -o /bin/go-vllm-api ./cmd/server

FROM ubuntu:22.04

RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list \
    && sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /bin/go-vllm-api /usr/local/bin/go-vllm-api

WORKDIR /app

EXPOSE 35001

ENTRYPOINT ["go-vllm-api"]
CMD ["--config", "/app/config.yaml", "--port", "35001"]
