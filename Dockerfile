FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install -e .

EXPOSE 8774

CMD ["python", "-m", "lvzhou", "serve", "--host", "0.0.0.0"]
