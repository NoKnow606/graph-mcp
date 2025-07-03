FROM python:3.13-alpine

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev python3-dev

# Upgrade pip
RUN pip install --upgrade pip

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install  --no-cache -r requirements.lock


# Default command
CMD ["python", "main.py"]