FROM python:3.12-slim-bookworm

RUN mkdir /datas
RUN mkdir /app
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY ./pyproject.toml /app/pyproject.toml
COPY ./uv.lock /app/uv.lock
RUN uv sync --locked --compile-bytecode

COPY ./static/ /app/static
COPY ./main.py /app/main.py

EXPOSE 8080

ENV ADMIN_USERNAME=Admin
ENV ADMIN_PASSWORD=pass

CMD ["uv", "run", "gunicorn", "--timeout", "0", "-w", "4", "-b", "0.0.0.0:8080", "main:app"]
