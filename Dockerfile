FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libreoffice \
    poppler-utils \
    && apt-get clean

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . .
EXPOSE 10000
CMD ["python", "app.py"]
