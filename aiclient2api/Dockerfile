# ── Stage 1: 编译 Go TLS sidecar ──
FROM golang:1.22-alpine AS sidecar-builder

ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV HTTP_PROXY=$HTTP_PROXY
ENV HTTPS_PROXY=$HTTPS_PROXY

RUN apk add --no-cache git

WORKDIR /build
COPY tls-sidecar/go.mod tls-sidecar/go.sum* ./
RUN go mod download || true

COPY tls-sidecar/ ./
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o tls-sidecar .

# ── Stage 2: Node.js 应用 ──
FROM node:20-alpine

LABEL maintainer="AIClient2API Team"
LABEL description="Docker image for AIClient2API server"

ARG HTTP_PROXY
ARG HTTPS_PROXY

RUN apk add --no-cache tar git procps

WORKDIR /app

COPY package*.json ./

RUN npm install || npm install --ignore-scripts

COPY . .

COPY --from=sidecar-builder /build/tls-sidecar /app/tls-sidecar/tls-sidecar
RUN chmod +x /app/tls-sidecar/tls-sidecar

USER root

RUN mkdir -p /app/logs

EXPOSE 3000 8085 8086 19876-19880

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node healthcheck.js || exit 1

CMD ["sh", "-c", "node src/core/master.js $ARGS"]
