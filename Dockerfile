FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# no correr como root dentro del contenedor
RUN useradd --create-home farmacia && mkdir /datos && chown farmacia /datos
USER farmacia
ENV DB_PATH=/datos/farmacia.db

EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/salud')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
