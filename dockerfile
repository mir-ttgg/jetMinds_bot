FROM python:3.10-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для безопасности
RUN useradd -m -u 1000 botuser

# Копирование зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY --chown=botuser:botuser . .

# Создание папок для логов
RUN mkdir -p /app/logs && \
    chown -R botuser:botuser /app/logs

# Переключение на непривилегированного пользователя
USER botuser

# Команда запуска
CMD ["python", "main.py"]