FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ESTATICOS_COMPRIMIDOS=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ .
# El código queda de root y de solo lectura; la app solo escribe en media/.
# Un volumen nuevo hereda ese dueño; uno anterior no (docs/despliegue.md).
RUN python manage.py collectstatic --noinput \
 && useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin oev \
 && mkdir -p media && chown oev:oev media
USER oev
