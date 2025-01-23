import os
from firebase_admin import storage
from werkzeug.utils import secure_filename
from firestore.cachemanager import filebase_app

def uploadArtifact(file):
    # Input: path of local image or video
    # Output: "status": "failure/success", "url": None, "error_message": any error message
    try:
        if not file:
            return {"status": "failure", "url": None, "error_message": "No file provided"}
        
        if file.filename == '':
            return {"status": "failure", "url": None, "error_message": "No file selected"}

        filename = secure_filename(file.filename)
        bucket = storage.bucket(app=filebase_app)
        blob = bucket.blob(f'uploads/{filename}')
        blob.upload_from_file(file, content_type=file.content_type)
        if os.getenv("STORAGE_EMULATOR_HOST", None):
            # If running on local, compose the url with local address
            url = os.getenv("STORAGE_EMULATOR_HOST", None) + f"/v0/b/{bucket.name}/o/uploads%2F{filename}?alt=media"
        else:
            # Using the actual storage on remote
            blob.make_public()
            url = blob.public_url        

        return {"status": "success", "url": url, "error_message": None}
    
    except Exception as e:
        return {"status": "failure", "url": None, "error_message": str(e)}
