## 🍻 Label Processor: Cloud Run and CV Pipeline

This project deploys a Python Flask application to Google Cloud Run that automatically processes image submissions from a Google Form. It uses Computer Vision (OpenCV) and OCR (Tesseract) to extract key data (Brand, Type, ABV, Volume) from beverage labels.
# 🚀 Architecture Overview

The system works as a three-stage webhook pipeline:

    Trigger (Google Apps Script): A Google Form submission triggers an Apps Script function.

    Request (Apps Script): The script extracts the Drive image link and POSTs the data to the Cloud Run endpoint.

    Processing (Cloud Run): The Flask app receives the request, downloads the image from Drive using a Service Account, runs the OpenCV/Tesseract processing pipeline, and extracts the label data.

# 🛠️ Prerequisites

    Google Cloud Project: A fully set up Google Cloud project with billing enabled.

    Google Cloud SDK (gcloud): Installed and authenticated locally.

    Docker: Installed and running locally.

    Python 3.11+: Installed locally for testing.

# ⚙️ Setup and Configuration
Phase 1: Google Cloud Setup
1. Enable APIs

Ensure the following APIs are enabled in your Google Cloud Project:
Bash

gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    drive.googleapis.com

2. Create and Configure a Service Account (SA)

The Service Account is required to allow your Cloud Run container to access files in Google Drive and to run the deployment.

    Navigate to IAM & Admin > Service Accounts in the Google Cloud Console.

    Create a new Service Account (e.g., ocr-processor-sa).

    Grant it the following roles:

        Cloud Run Invoker (If you want other services to call it)

        Service Account User (So Cloud Run can deploy with it)

        Storage Admin (For GCR/Artifact Registry access during deployment)

    Grant Drive Access: Find the email address of your new Service Account (e.g., ocr-processor-sa@your-project-id.iam.gserviceaccount.com).

    Share the Google Drive Folder: Go to the Google Drive folder where your submitted images will land (the folder associated with your Google Form) and share it with the Service Account email address, granting it Viewer access.

3. (Optional: Local Testing) Download Service Account Key

If you plan to run app.py locally before deployment:

    In the Service Account detail page, go to Keys.

    Click Add Key > Create New Key > JSON.

    Download the JSON file and save it locally.

    Update the path in app.py:
    Python

    SERVICE_ACCOUNT_FILE = 'C:/Users/clcas/ttb/exclude/service_account_key.json' 

Phase 2: Local Project Setup

Create a new directory for your project and save the three provided files inside it:

    Dockerfile

    requirements.txt

    app.py (The final merged code)

Phase 3: Build and Deploy

Navigate to your project directory in your terminal. Replace the placeholder values in the commands below ([PROJECT-ID], [SERVICE-NAME], [REGION], and [SA-EMAIL]).
1. Build and Push the Docker Image

This step builds the container and stores it in your project's Google Container Registry (GCR).
Bash

# Example: gcloud builds submit --tag gcr.io/my-project/label-ocr --region=us-central1
gcloud builds submit --tag gcr.io/[PROJECT-ID]/[SERVICE-NAME] --region=[REGION]

2. Deploy to Cloud Run

This deploys the image to a new Cloud Run service, setting the correct permissions and authentication.
Bash

gcloud run deploy [SERVICE-NAME] \
  --image gcr.io/[PROJECT-ID]/[SERVICE-NAME] \
  --region [REGION] \
  --platform managed \
  --allow-unauthenticated \
  --service-account [SA-EMAIL]

Note: The --allow-unauthenticated flag is required because the request is coming from Google Apps Script, which is an external (unauthenticated) source.
3. Retrieve the Service URL

The command output will give you the live service URL. Note it down!
Bash

gcloud run services describe [SERVICE-NAME] --region [REGION] --format 'value(status.url)'

Phase 4: Google Apps Script Webhook

The last step is to configure your Google Form/Sheet to trigger the Cloud Run endpoint.

    Open your Google Sheet linked to the form.

    Go to Extensions > Apps Script.

    Paste the provided Apps Script code into the Code.gs file.

    Crucially, update the URL:
    JavaScript

    // Update this line with the full URL from Phase 3, Step 3
    var pythonScriptUrl = "YOUR_CLOUD_RUN_SERVICE_URL"; 

    // Ensure the final fetch URL looks like:
    // "https://your-service-hash.region.a.run.app/new_submission_hook"

    Set the Trigger:

        In the Apps Script editor, click the Clock icon (Triggers) on the left sidebar.

        Click Add Trigger.

        Set Choose which function to run to onFormSubmit.

        Set Choose event source to From spreadsheet.

        Set Choose event type to On form submit.

        Click Save. (You may need to grant permissions the first time.)

Your entire pipeline is now live. Every time the Google Form receives a submission, it will send the data to your Cloud Run service for processing.
