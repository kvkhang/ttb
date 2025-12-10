# Use the official Python base image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# 1. Install System Dependencies (REQUIRED for OpenCV and Tesseract)
# 'apt-get update' refreshes package lists.
# 'tesseract-ocr' is the underlying OCR executable for pytesseract.
# 'libtesseract-dev' is required for the Python pytesseract wrapper.
# 'libgl1' is often required for headless OpenCV.
RUN apt-get update && \
    apt-get install -y tesseract-ocr libtesseract-dev libgl1 && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY requirements.txt .

# Use --no-cache-dir to keep the image size small
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app.py .

# Define the port your app will listen on (8080 is the default for Cloud Run)
ENV PORT 8080

# Command to run the application using Gunicorn
# 1 worker and 8 threads is a good starting point for a high-concurrency Cloud Run service
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app