# Используем легкий образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем список зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем папки для кэша и временных файлов
RUN mkdir -p cache scratch

# Команда для запуска (по умолчанию запускает основной пайплайн)
# В GitHub Actions мы будем переопределять запуск, если нужно
CMD ["python", "main.py"]
