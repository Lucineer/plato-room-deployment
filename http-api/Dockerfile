FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn pyyaml

COPY http-api/plato_server.py /app/plato_server.py

# Mount rooms directory
VOLUME /srv/plato-rooms

ENV PLATO_ROOMS_DIR=/srv/plato-rooms
ENV PLATO_PORT=8100

EXPOSE 8100

CMD ["python3", "plato_server.py", "--rooms-dir", "/srv/plato-rooms", "--host", "0.0.0.0"]
