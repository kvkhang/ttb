import cv2
import numpy as np
import matplotlib.pyplot as plt
import pytesseract
from PIL import Image
import re
import os
import sys

# --- CONFIGURATION ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Add error handling for image loading
img_path = "C:/Users/clcas/ttb/exclude/IMG_5272.jpg"
img = cv2.imread(img_path, cv2.IMREAD_COLOR)

if img is None:
    print(f"Error loading image from {img_path}", file=sys.stderr)
    sys.exit()

(h, w) = img.shape[:2]

# --- HELPER FUNCTION 1: CATEGORICAL PARSING ---
def extract_brand_and_type(text):
    """Extracts Brand (CAPS) and known Product Type from raw OCR text."""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    brand = None
    product_type = None

    for line in lines:
        if line.isupper() and len(line) > 3:
            brand = line.split()[0] # Take the first word of the capitalized line
            break
        
    # Search for known product types (case-insensitive)
    # BEER|LAGER|ALE|STOUT|IPA|WINE|SPIRIT are common alcohol types
    match = re.search(r'(BEER|LAGER|ALE|STOUT|IPA|WINE|SPIRIT)', text, re.IGNORECASE)
    if match:
        product_type = match.group(1).upper()
        
    return brand, product_type

# --- HELPER FUNCTION 2: NUMERICAL PARSING (Works on the full merged text) ---
def extract_numerical_data(text):
    """Extracts ABV and Volume regardless of position in the text."""
    results = {'volume_fl_oz': None, 'volume_ml': None, 'abv': None}
    
    # Use the robust error replacement strategy for common OCR mistakes on metal
    text_for_abv_parsing = text.replace('S', '4').replace('K', '.') 

    # 1. Volume Extraction (FL OZ)
    fl_oz_match = re.search(r'(\d+)\s*FL\.?OZ', text, re.IGNORECASE)
    if fl_oz_match:
        results['volume_fl_oz'] = int(fl_oz_match.group(1))

    # 2. Volume Extraction (ML) - Looking for 3+ digits followed by ML or IAL/M.L.
    ml_match = re.search(r'(\d{3,})\s*(ML|IAL|M\.L\.)', text, re.IGNORECASE)
    if ml_match:
        results['volume_ml'] = int(ml_match.group(1))

    # 3. ABV Extraction (e.g., 4.9% or 4.9 ALC)
    abv_match = re.search(r'(\d\.\d)\s*[A-Z%]*\s*(ALC|NOL|VOL)', text_for_abv_parsing, re.IGNORECASE)
    if abv_match:
        results['abv'] = float(abv_match.group(1))
        
    return results


# --- MAIN PROCESSING FUNCTION ---
def process_label_data(original_image):
    """
    Executes dual-region OCR, merges the text outputs, and runs unified parsing.
    """
    (h, w) = original_image.shape[:2]
    all_ocr_outputs = [] # List to store raw text from all passes
    
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
    final_brand_image = cv2.bitwise_not(cleaned_brand_image) # Invert for light on dark text

    raw_text_brand = pytesseract.image_to_string(Image.fromarray(final_brand_image), config=r'--psm 3')
    all_ocr_outputs.append(raw_text_brand)

    # ----------------------------------------------------
    # *** MERGE OCR OUTPUTS AND RUN UNIVERSAL PARSING ***
    # ----------------------------------------------------
    
    # Combine the text from all successful OCR passes into one string
    merged_raw_text = ' '.join(all_ocr_outputs) 
    cleaned_merged_text = merged_raw_text.replace('\n', ' ').strip()
    
    # 1. Extract Categorical Data (Brand/Type)
    brand_name, product_type = extract_brand_and_type(cleaned_merged_text)
    
    # 2. Extract Numerical Data (Volume/ABV)
    numerical_data = extract_numerical_data(cleaned_merged_text)
    
    # Final Result Dictionary
    results = {
        'brand': brand_name,
        'product_type': product_type,
        **numerical_data # Merge the dictionary of numerical data
    }

    return results

# --- EXECUTION ---
if __name__ == '__main__':
    final_data = process_label_data(img)
    
    print("\n--- FINAL MERGED EXTRACTION RESULTS ---")
    print(f"Brand: {final_data['brand']}")
    print(f"Product Type: {final_data['product_type']}")
    print(f"Volume (FL OZ): {final_data['volume_fl_oz']}")
    print(f"Volume (ML): {final_data['volume_ml']}")
    print(f"ABV: {final_data['abv']}%")

    # --- Verification Example (Phase 3) ---
    # This verification logic is now clean and easy to read!
    if final_data['brand'] == 'SAPPORO' and final_data['product_type'] == 'BEER' and final_data['abv'] == 4.9:
        print("\n✅ Verification Success: Matches SAPPORO BEER standard.")
    else:
        print("\n❌ Verification Failed: Data mismatch.")