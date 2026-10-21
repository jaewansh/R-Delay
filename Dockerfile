FROM python:3.12-slim
WORKDIR /app
COPY requirements-service.txt ./
RUN pip install --no-cache-dir -r requirements-service.txt
COPY engine ./engine
COPY api ./api
COPY web ./web
ARG SOURCE_COMMIT=unavailable
ENV RDELAY_SOURCE_COMMIT=$SOURCE_COMMIT PYTHONUNBUFFERED=1
RUN useradd --uid 10001 --create-home rdelay
USER rdelay
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
