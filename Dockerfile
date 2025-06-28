FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app

WORKDIR /app

RUN mkdir /datas

RUN uv sync --locked --compile-bytecode

EXPOSE 8080

ENV ADMIN_USERNAME=Admin
ENV ADMIN_PASSWORD=pass

CMD ["uv", "run", "gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "main:app"]
