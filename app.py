from flask import Flask, request, jsonify
import json
import os
import sys # <-- NEW IMPORT

app = Flask(__name__)

# Function to ensure output goes to stderr
def log_to_stderr(message):
    """Writes a message to the standard error stream."""
    sys.stderr.write(message + '\n')
    sys.stderr.flush() # Ensures the message is sent immediately

# --- Processing Logic ---
def process_new_submission(row_number, submission_values):
    # CHANGED: Using log_to_stderr instead of print()
    log_to_stderr(f"--- DEBUG: NEW FORM SUBMISSION (Row: {row_number}) ---")
    
    # Example: Split the pipe-separated data and log the image link
    data_list = submission_values.split('|')
    log_to_stderr(f"DEBUG: Timestamp: {data_list[0]}")
    
    if len(data_list) > 2:
        image_link = data_list[2] 
        log_to_stderr(f"DEBUG: Image Link: {image_link}")
        # ... your file ID extraction logic here ...
    else:
        log_to_stderr(f"DEBUG: ERROR - Submission data was incomplete for row {row_number}.")
        
    return f"Processed row {row_number} successfully."


# --- Webhook Handler ---
@app.route('/new_submission_hook', methods=['POST'])
def handle_webhook():
    try:
        raw_data = request.get_data(as_text=True)
        data = json.loads(raw_data)
        
        row_num = data.get('row')
        submission_values = data.get('data')

        if not row_num or not submission_values:
            # Using log_to_stderr for debugging failure
            log_to_stderr(f"ERROR: Missing row or data key. Raw payload: {raw_data}") 
            return jsonify({'error': 'Missing data in payload'}), 400

        result_message = process_new_submission(row_num, submission_values)
        
        return jsonify({'status': 'success', 'message': result_message}), 200
        
    except Exception as e:
        # Using log_to_stderr for exceptions
        log_to_stderr(f"FATAL ERROR in handle_webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ... (The rest of your boilerplate Flask code remains the same) ...

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)