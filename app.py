from flask import Flask, request, jsonify
import json
import os
import sys

# --- GOOGLE API IMPORTS ---
import io
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- COMPUTER VISION & OCR IMPORTS ---
import cv2
import numpy as np
from PIL import Image
import pytesseract

# --- FLASK APP SETUP ---
app = Flask(__name__)

# Function to ensure output goes to stderr (REQUIRED for Cloud Run logging)
def log_to_stderr(message):
    """Writes a message to the standard error stream."""
    sys.stderr.write(message + '\n')
    sys.stderr.flush()

# --- CONFIGURATION & AUTH SETUP (Executed once at startup) ---

# Tesseract Path (Only used for local testing; removed for clean Cloud Run deployment)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 1. Service Account Setup (REQUIRED for Google Drive access)
# IMPORTANT: When deployed to Cloud Run, this file will NOT exist. 
# Cloud Run automatically handles credentials if the Service Account is set correctly.
SERVICE_ACCOUNT_FILE = 'C:/Users/clcas/ttb/exclude/service_account_key.json' 
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

try:
    # Load credentials explicitly for LOCAL TESTING
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=DRIVE_SCOPES)
    DRIVE_SERVICE = build('drive', 'v3', credentials=creds) 
    log_to_stderr("DEBUG: Running in LOCAL mode with Service Account credentials.")

except FileNotFoundError:
    # This block handles the Cloud Run scenario where the file is absent, 
    # and default application credentials (from the Service Account role) are used.
    log_to_stderr("DEBUG: Service Account file not found. Assuming Cloud Run or default environment auth.")
    from google.auth import default as google_default_auth
    
    # Use default auth for Cloud Run environment
    creds, _ = google_default_auth(scopes=DRIVE_SCOPES)
    DRIVE_SERVICE = build('drive', 'v3', credentials=creds)


# --- GOOGLE DRIVE DOWNLOAD FUNCTION ---

def download_image_to_buffer(image_link):
    """Downloads the image from a Drive URL into an in-memory buffer (io.BytesIO)."""
    
    match = re.search(r'id=([A-Za-z0-9_-]+)', image_link)
    if not match:
        raise ValueError(f"Invalid Drive URL format received: {image_link}")

    file_id = match.group(1)
    
    try:
        request = DRIVE_SERVICE.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        
        while not done:
            _, done = downloader.next_chunk()
            
        fh.seek(0)
        return fh

    except Exception as e:
        if "404" in str(e) or "403" in str(e):
             raise PermissionError(f"Drive API access denied for ID: {file_id}. Check Service Account file sharing.")
        else:
            raise Exception(f"Drive download failed: {e}")


# --- HELPER FUNCTION 1: CATEGORICAL PARSING ---
def extract_brand_and_type(text):
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    brand = None
    product_type = None

    for line in lines:
        if line.isupper() and len(line) > 3:
            brand = line.split()[0]
            break
        
    match = re.search(r'(BEER|LAGER|ALE|STOUT|IPA|WINE|SPIRIT)', text, re.IGNORECASE)
    if match:
        product_type = match.group(1).upper()
        
    return brand, product_type

# --- HELPER FUNCTION 2: NUMERICAL PARSING ---
def extract_numerical_data(text):
    results = {'volume_fl_oz': None, 'volume_ml': None, 'abv': None}
    
    text_for_abv_parsing = text.replace('S', '4').replace('K', '.') 

    fl_oz_match = re.search(r'(\d+)\s*FL\.?OZ', text, re.IGNORECASE)
    if fl_oz_match:
        results['volume_fl_oz'] = int(fl_oz_match.group(1))

    ml_match = re.search(r'(\d{3,})\s*(ML|IAL|M\.L\.)', text, re.IGNORECASE)
    if ml_match:
        results['volume_ml'] = int(ml_match.group(1))

    abv_match = re.search(r'(\d\.\d)\s*[A-Z%]*\s*(ALC|NOL|VOL)', text_for_abv_parsing, re.IGNORECASE)
    if abv_match:
        results['abv'] = float(abv_match.group(1))
        
    return results

# --- MAIN PROCESSING FUNCTION (CV/OCR) ---

def process_label_data(original_image):
    (h, w) = original_image.shape[:2]
    all_ocr_outputs = [] 
    
    # --- PASS 1: NUMERICAL DATA AREA (Bottom 30%) ---
    crop_start_y = int(h * 0.70)
    cropped_image_num = original_image[crop_start_y:h, :]
    
    gray_num = cv2.cvtColor(cropped_image_num, cv2.COLOR_BGR2GRAY)
    blurred_num = cv2.medianBlur(gray_num, 3)
    cleaned_image_num = cv2.adaptiveThreshold(blurred_num, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7)

    raw_text_num = pytesseract.image_to_string(Image.fromarray(cleaned_image_num), config=r'--psm 11')
    all_ocr_outputs.append(raw_text_num)

    # --- PASS 2: CATEGORICAL DATA AREA (Top 65%) ---
    crop_end_y_brand = int(h * 0.65)
    cropped_brand_image = original_image[0:crop_end_y_brand, :]
    
    gray_brand = cv2.cvtColor(cropped_brand_image, cv2.COLOR_BGR2GRAY)
    blurred_brand = cv2.medianBlur(gray_brand, 5)
    
    cleaned_brand_image = cv2.adaptiveThreshold(blurred_brand, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 10)
    final_brand_image = cv2.bitwise_not(cleaned_brand_image)

    raw_text_brand = pytesseract.image_to_string(Image.fromarray(final_brand_image), config=r'--psm 3')
    all_ocr_outputs.append(raw_text_brand)

    # --- MERGE OCR OUTPUTS AND RUN UNIVERSAL PARSING ---
    merged_raw_text = ' '.join(all_ocr_outputs) 
    cleaned_merged_text = merged_raw_text.replace('\n', ' ').strip()
    
    brand_name, product_type = extract_brand_and_type(cleaned_merged_text)
    numerical_data = extract_numerical_data(cleaned_merged_text)
    
    results = {
        'brand': brand_name,
        'product_type': product_type,
        **numerical_data
    }

    return results


# --- Webhook Handler (Main Entry Point) ---

def process_new_submission(row_number, submission_values):
    log_to_stderr(f"--- START PROCESSING ROW {row_number} ---")
    
    data_list = submission_values.split('|')
    
    if len(data_list) < 7:
        log_to_stderr(f"ERROR: Submission data incomplete for row {row_number}.")
        return "ERROR: Submission data incomplete."
        
    image_link = data_list[7] 
    log_to_stderr(f"DEBUG: Image Link: {image_link}")

    try:
        # Step 1: Download image from Drive into a memory buffer
        image_buffer = download_image_to_buffer(image_link)
        buffer_bytes = image_buffer.getvalue()
        log_to_stderr(f"DEBUG: Download successful. Buffer size: {len(buffer_bytes)} bytes.")

        # Step 2: Decode the buffer bytes into an OpenCV image array
        image_bytes = np.frombuffer(buffer_bytes, np.uint8)
        original_image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)

        if original_image is None:
             raise ValueError("OpenCV failed to decode the downloaded image.")
        
        # Step 3: Run the full CV/OCR processing pipeline
        final_data = process_label_data(original_image)
        log_to_stderr(f"DEBUG: Extracted Data: {final_data}")

        # You would typically send this data to a database or verification system here.
        
        return f"Successfully processed row {row_number}. Extracted Brand: {final_data['brand']}, ABV: {final_data['abv']}%"

    except Exception as e:
        log_to_stderr(f"FAILURE during image processing for row {row_number}: {e}")
        return f"Processing failed for row {row_number}: {str(e)}"


# --- Flask Routing ---

@app.route('/new_submission_hook', methods=['POST'])
def handle_webhook():
    try:
        raw_data = request.get_data(as_text=True)
        data = json.loads(raw_data)
        
        row_num = data.get('row')
        submission_values = data.get('data')

        if not row_num or not submission_values:
            log_to_stderr(f"ERROR: Missing row or data key. Raw payload: {raw_data}") 
            return jsonify({'error': 'Missing data in payload'}), 400

        result_message = process_new_submission(row_num, submission_values)
        
        return jsonify({'status': 'success', 'message': result_message}), 200
        
    except Exception as e:
        log_to_stderr(f"FATAL ERROR in handle_webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# --- Flask Run ---

if __name__ == '__main__':
    # Cloud Run uses the PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    # Note: When deploying to Cloud Run, the app is served via a reverse proxy (Gunicorn), 
    # but for local testing, this run command is fine.
    log_to_stderr(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port)