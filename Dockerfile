FROM python:slim

WORKDIR /app
COPY register register
COPY config.py .
COPY reports_endpoint.py .
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

CMD ["sh", "-c", "python reports_endpoint.py"]