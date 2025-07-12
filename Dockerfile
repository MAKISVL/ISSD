FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# ИЗМЕНЕНИЕ ЗДЕСЬ: Запускаем gunicorn как Python-модуль
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:5000", "app:app"]