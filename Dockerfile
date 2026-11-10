FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ESTATICOS_COMPRIMIDOS=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ .
# El código queda de root y solo lectura para la app; lo único que escribe es
# media/, que en el servidor es un volumen. Un volumen nuevo hereda este dueño;
# uno creado antes, no (ver "Usuario del contenedor" en docs/despliegue.md).
RUN python manage.py collectstatic --noinput \
 && useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin oev \
 && mkdir -p media && chown oev:oev media
USER oev
