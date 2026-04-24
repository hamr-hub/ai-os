FROM golang:1.25-alpine AS builder

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories \
    && apk update && apk add --no-cache git gcc musl-dev

ENV GOPROXY=https://goproxy.cn,direct

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /bin/go-vllm-api ./cmd/server

FROM alpine:3.20

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories \
    && apk add --no-cache ca-certificates tzdata

COPY --from=builder /bin/go-vllm-api /usr/local/bin/go-vllm-api
COPY configs/config.yaml /app/configs/config.yaml

WORKDIR /app

EXPOSE 35001

ENTRYPOINT ["go-vllm-api"]
CMD ["--config", "configs/config.yaml", "--port", "35001"]
