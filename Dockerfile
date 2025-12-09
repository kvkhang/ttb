# Use the official Python base image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app.py .

# Define the port your app will listen on (8080 is the default for Cloud Run)
ENV PORT 8080

# Command to run the application using Gunicorn
# Gunicorn is a production-ready web server that runs your Flask app
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app