import io
import re
from google.oauth2 import service_account  # <-- NEW: Required for Service Account JSON
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import sys

# --- CONFIGURATION ---
# IMPORTANT: This path must be correct on your local machine
SERVICE_ACCOUNT_FILE = 'C:/Users/clcas/ttb/exclude/service_account_key.json' 
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


# 1. LOAD CREDENTIALS EXPLICITLY FROM JSON KEY
try:
    # Use service_account.Credentials.from_service_account_file to load the JSON key
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=DRIVE_SCOPES)
except FileNotFoundError:
    print(f"ERROR: Service account key file not found at {SERVICE_ACCOUNT_FILE}", file=sys.stderr)
    sys.exit()

# 2. BUILD SERVICE USING THE EXPLICITLY LOADED CREDS
# This replaces the line that previously used google.auth.default()
DRIVE_SERVICE = build('drive', 'v3', credentials=creds) 


def download_and_preprocess_image(image_link):
    """
    1. Extracts the File ID from the URL.
    2. Downloads the file content to a memory buffer (fh) using the authenticated
       Service Account.
    """
    
    # --- 1. EXTRACT FILE ID ---
    # The ID is the unique string after 'id='
    match = re.search(r'id=([A-Za-z0-9_-]+)', image_link)
    if not match:
        raise ValueError(f"Invalid Drive URL format received: {image_link}")

    file_id = match.group(1)
    print(f"DEBUG: Extracted File ID: {file_id}")
    
    # --- 2. DOWNLOAD FILE TO MEMORY BUFFER ---
    try:
        request = DRIVE_SERVICE.files().get_media(fileId=file_id)
        fh = io.BytesIO() # The in-memory buffer that holds the file
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        
        while not done:
            status, done = downloader.next_chunk()
            # Optional: Log progress here if files are huge
            
        fh.seek(0) # IMPORTANT: Reset buffer pointer to the beginning
        
        # Now, fh contains the raw image data (bytes)
        return fh

    except Exception as e:
        # Check if the error is due to permissions
        if "404" in str(e) or "403" in str(e):
             # Reraise as PermissionError for easier local debugging
             raise PermissionError(f"Drive API access denied. File ID: {file_id}. Ensure service account has viewer permissions on file/folder.")
        else:
            raise Exception(f"Drive download failed: {e}")


# --- Integration Example in Your Main Function ---

def process_new_submission(row_number, submission_values):
    # This function is where the full submission processing would happen
    # 1. Split and find the image link (assuming it's at index 2 for now)
    data_list = submission_values.split('|')
    image_link = data_list[2] 
    
    # 2. Download the image file into a memory buffer
    image_buffer = download_and_preprocess_image(image_link)
    
    # 3. Use the buffer bytes to start your CV process (Phase 1)
    buffer_bytes = image_buffer.getvalue()
    
    # Your CV code starts here:
    # image_bytes = np.frombuffer(buffer_bytes, np.uint8)
    # original_image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
    # ... and so on
    
    return "Download complete. Ready for CV."

# --- Execution for Local Test ---
# Use the same image link you were testing with
if __name__ == '__main__':
    try:
        image_buffer = download_and_preprocess_image("https://drive.google.com/open?id=1srzd6hmqfhsr1O-FptGCDVdIc2C79T9f")
        
        # If the code reaches here, the download was successful!
        print("\n✅ SUCCESS: Image downloaded successfully into memory buffer.")
        print(f"Buffer size (bytes): {len(image_buffer.getvalue())}")
        
    except Exception as e:
        print(f"\n❌ FAILURE: {e}")