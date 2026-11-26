FROM node:24-alpine AS frontend-build
WORKDIR /app/frontend
ARG VITE_CONTACT_EMAIL
ENV VITE_CONTACT_EMAIL=${VITE_CONTACT_EMAIL}
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
EXPOSE 10000
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","10000"]
