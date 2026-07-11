FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV RENTAL_DEMO_MODE=true
ENV GROQ_MODEL=llama-3.1-8b-instant

WORKDIR /app

COPY rental-housing-system/backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY rental-housing-system /app/rental-housing-system

WORKDIR /app/rental-housing-system

EXPOSE 7860

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
