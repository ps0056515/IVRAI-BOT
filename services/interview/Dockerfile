FROM python:3.11-slim

WORKDIR /app

COPY services/interview/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/interview/ /app/

EXPOSE 8000

ENV INTERVIEW_PORT=8000
ENV VOICE_WS_PUBLIC_URL=ws://localhost:8765
ENV VOICE_HTTP_PUBLIC_URL=http://localhost:8081

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
