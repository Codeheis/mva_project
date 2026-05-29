FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements and source code
COPY . /app

# Install all dependencies in one step and fix the bcrypt version conflict
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    sqlalchemy \
    psycopg2-binary \
    passlib[bcrypt] \
    python-jose[cryptography] \
    email-validator \
    python-multipart \
    bcrypt==4.0.1

# Expose FastAPI port
EXPOSE 8001

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
