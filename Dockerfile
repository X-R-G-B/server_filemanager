FROM debian:12-slim AS base

RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get install -y \
        libssl-dev

FROM base AS builder

RUN apt-get install -y \
        gcc \
        make \
        git
RUN git clone --depth=1 https://github.com/vlang/v /v
RUN make -C /v
RUN mkdir /app
COPY ./main.v /app/main.v
COPY ./v.mod /app/v.mod
COPY ./static/ /app/static
RUN cd /app && /v/v -prod -d use_openssl -o server_filemanager .

FROM base AS production

RUN mkdir /app
WORKDIR /app
RUN mkdir /datas
COPY --from=builder /app/server_filemanager /app/server_filemanager
EXPOSE 8080
ENV ADMIN_USERNAME=Admin
ENV ADMIN_PASSWORD=pass
CMD ["./server_filemanager"]
