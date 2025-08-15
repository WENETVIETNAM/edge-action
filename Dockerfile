FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main script
COPY main.py .

# Make the script executable
RUN chmod +x main.py

# Set the entrypoint
ENTRYPOINT ["python", "/app/main.py"]