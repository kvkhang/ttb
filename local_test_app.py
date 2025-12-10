import sys
import os

# --- CORE PROCESSING IMPORTS ---
import cv2
import numpy as np
from PIL import Image
import pytesseract
import re

# --- SIMPLIFIED LOGGING ---
def log_message(message):
    """Writes a message to the standard output stream."""
    print(message)

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
    
    # Text cleaning tailored for common OCR mistakes
    text_for_abv_parsing = text.replace('S', '4').replace('K', '.') 

    fl_oz_match = re.search(r'(\d+)\s*FL\.?OZ', text, re.IGNORECASE)
    if fl_oz_match:
        results['volume_fl_oz'] = int(fl_oz_match.group(1))

    ml_match = re.search(r'(\d{3,})\s*(ML|IAL|M\.L\.)', text, re.IGNORECASE)
    if ml_match:
        results['volume_ml'] = int(ml_match.group(1))

    # Pattern for X.X% or X.X ALC/VOL/NOL
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
    # Binary Thresholding for clear text detection
    cleaned_image_num = cv2.adaptiveThreshold(blurred_num, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7)

    # Use PSM 11 for finding single words or lines (good for numerical data)
    raw_text_num = pytesseract.image_to_string(Image.fromarray(cleaned_image_num), config=r'--psm 11')
    all_ocr_outputs.append(raw_text_num)

    # --- PASS 2: CATEGORICAL DATA AREA (Top 65%) ---
    crop_end_y_brand = int(h * 0.65)
    cropped_brand_image = original_image[0:crop_end_y_brand, :]
    
    gray_brand = cv2.cvtColor(cropped_brand_image, cv2.COLOR_BGR2GRAY)
    blurred_brand = cv2.medianBlur(gray_brand, 5)
    
    cleaned_brand_image = cv2.adaptiveThreshold(blurred_brand, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 10)
    # Invert the image if text is light on dark background (common for labels)
    final_brand_image = cv2.bitwise_not(cleaned_brand_image)

    # Use PSM 3 for fully automatic page segmentation (good for main text blocks)
    raw_text_brand = pytesseract.image_to_string(Image.fromarray(final_brand_image), config=r'--psm 3')
    all_ocr_outputs.append(raw_text_brand)

    # --- MERGE OCR OUTPUTS AND RUN UNIVERSAL PARSING ---
    merged_raw_text = ' '.join(all_ocr_outputs) 
    log_message(f"\n--- RAW OCR OUTPUT ---\n{merged_raw_text}\n----------------------")
    
    brand_name, product_type = extract_brand_and_type(merged_raw_text)
    numerical_data = extract_numerical_data(merged_raw_text)
    
    results = {
        'brand': brand_name,
        'product_type': product_type,
        **numerical_data
    }

    return results

# --- MAIN EXECUTION BLOCK ---
if __name__ == '__main__':
    # Add Tesseract Path for local Windows users (comment out for Linux/Docker)
    # pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'

    if len(sys.argv) < 2:
        log_message("Usage: python local_test_app.py <path_to_image_file>")
        sys.exit(1)
        
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        log_message(f"Error: Image file not found at path: {image_path}")
        sys.exit(1)

    log_message(f"--- STARTING LOCAL IMAGE PROCESSING ---")
    log_message(f"Image Path: {image_path}")

    try:
        # Step 1: Read the image directly from the file system
        original_image = cv2.imread(image_path, cv2.IMREAD_COLOR)

        if original_image is None:
            raise ValueError(f"OpenCV failed to read or decode the image at {image_path}.")
        
        log_message(f"Image loaded successfully. Dimensions: {original_image.shape}")

        # Step 2: Run the full CV/OCR processing pipeline
        final_data = process_label_data(original_image)
        
        # Step 3: Print final results
        log_message("\n====================================")
        log_message("✅ PROCESSING COMPLETE: EXTRACTED DATA")
        log_message("====================================")
        log_message(f"Brand:        {final_data['brand']}")
        log_message(f"Product Type: {final_data['product_type']}")
        log_message(f"ABV:          {final_data['abv']}")
        log_message(f"Volume (ml):  {final_data['volume_ml']}")
        log_message(f"Volume (fl oz): {final_data['volume_fl_oz']}")
        log_message("====================================")

    except Exception as e:
        log_message(f"\nFATAL ERROR during image processing: {e}")
        sys.exit(1)