# Base Image
FROM python:3.10-slim

# Working Directory
WORKDIR /app

# Install system dependencies (gcc for building some python packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Requirements
COPY requirements_web.txt .

# Install Python Dependencies
# We use --no-cache-dir to keep image small
RUN pip3 install --no-cache-dir -r requirements_web.txt

# Copy Application Code
COPY . .

# Expose Streamlit Port
EXPOSE 8501

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Command
ENTRYPOINT ["streamlit", "run", "web_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
