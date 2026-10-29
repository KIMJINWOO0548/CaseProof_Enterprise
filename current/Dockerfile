FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY service/ service/
COPY reference/ reference/
COPY datasets/ datasets/
ENV CASEPROOF_DEMO_MODE=1
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
