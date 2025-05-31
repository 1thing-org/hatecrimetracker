import firebase_admin
from firebase_admin import credentials, firestore
import os

# --- ⚙️ START OF CONFIGURATION ⚙️ ---
# Modify the values below according to your needs.

# Source Project Configuration
SOURCE_PROJECT_KEY_FILE = "./hate-crime-tracker-7d52738f7212.json" # 👈 Replace with actual path
SOURCE_COLLECTION_NAME = "incident" # 👈 Replace with your source collection name

# Target Configuration
# Choose target type:
# "CLOUD" for another Google Cloud Firebase project
# "EMULATOR" for a local Firebase Emulator
TARGET_TYPE = "CLOUD"  # 👈 Or "EMULATOR"

TARGET_COLLECTION_NAME = "incident_copy" # 👈 Replace with your target collection name

# Target: Google Cloud Firebase Project (only if TARGET_TYPE is "CLOUD")
TARGET_PROJECT_KEY_FILE = "./hate-crime-tracker-dev-c004beb9b795.json" # 👈 Replace if TARGET_TYPE is "CLOUD"

# Target: Local Firebase Emulator (only if TARGET_TYPE is "EMULATOR")
# The script will first check for FIRESTORE_EMULATOR_HOST environment variable.
# If not set, it will use the value below.
# Example: "localhost:8080"
EMULATOR_HOST_OVERRIDE = "localhost:8080" # 👈 Set if FIRESTORE_EMULATOR_HOST env var isn't preferred/set
# Project ID to use for the emulator (can be a dummy one)
EMULATOR_PROJECT_ID = "my-emulator-project" # 👈 Replace if TARGET_TYPE is "EMULATOR"
# For emulator, the SDK needs a structurally valid service account JSON.
# You can reuse the source key, or provide a path to any valid service account JSON.
EMULATOR_DUMMY_KEY_FILE = TARGET_PROJECT_KEY_FILE # Often okay to reuse source or any valid key for structure

# Batch size for writing documents
BATCH_WRITE_SIZE = 5


# --- ⚙️ END OF CONFIGURATION ⚙️ ---
def initialize_app(service_account_key_path, app_name, project_id=None):
    """Initializes a Firebase app instance."""
    try:
        # Check if app already initialized with the same name, delete if so.
        # This allows re-running the script with potentially different configurations.
        try:
            existing_app = firebase_admin.get_app(name=app_name)
            if existing_app:
                firebase_admin.delete_app(existing_app)
                print(f"Deleted existing Firebase app '{app_name}' to re-initialize.")
        except ValueError:
            pass # App doesn't exist yet, no need to delete

        cred = credentials.Certificate(service_account_key_path)
        if project_id: # For specific project ID, especially useful for emulator
            app = firebase_admin.initialize_app(cred, {
                'projectId': project_id,
            }, name=app_name)
        else:
            app = firebase_admin.initialize_app(cred, name=app_name)
        print(f"Firebase app '{app_name}' initialized successfully.")
        return app
    except Exception as e:
        print(f"Error initializing Firebase app '{app_name}': {e}")
        return None

def copy_collection(source_db, target_db, source_collection_name, target_collection_name, batch_size=500):
    """
    Copies all documents from a source collection to a target collection.

    Args:
        source_db: Firestore client for the source project.
        target_db: Firestore client for the target project or emulator.
        source_collection_name (str): Name of the collection to copy from.
        target_collection_name (str): Name of the collection to copy to.
        batch_size (int): Number of documents to write in a single batch.
    """
    print(f"\nStarting copy from '{source_collection_name}' to '{target_collection_name}'...")

    try:
        source_coll_ref = source_db.collection(source_collection_name)
        docs = source_coll_ref.stream() # Use stream() for large collections

        count = 0
        batch = target_db.batch()
        target_coll_ref = target_db.collection(target_collection_name)

        for doc in docs:
            doc_ref = target_coll_ref.document(doc.id) # Preserve document IDs
            batch.set(doc_ref, doc.to_dict())
            print(f"Copied document ID: {doc.id} to target collection '{target_collection_name}'")
            # print(f"Document data: {doc.to_dict()}")
            count += 1

            if count % batch_size == 0:
                batch.commit()
                print(f"Committed batch of {batch_size} documents. Total copied: {count}")
                batch = target_db.batch() # Start a new batch

        # Commit any remaining documents in the last batch
        if count > 0 and count % batch_size != 0: # ensure batch is not empty
            batch.commit()
            print(f"Committed final batch. Total documents copied: {count}")
        elif count == 0:
             print(f"No documents found in source collection '{source_collection_name}'.")


        if count > 0:
            print(f"\nSuccessfully copied {count} documents from '{source_collection_name}' to '{target_collection_name}'. ✨")

    except Exception as e:
        print(f"An error occurred during the copy process: {e}")

def main():
    """Main function to drive the copy process."""

    print("Firebase Collection Copier 📂➡️📂")
    print("---------------------------------")

    


    # --- Initialize Source Firebase App ---
    source_app_name = "hate-crime-tracker"
    source_app = initialize_app(SOURCE_PROJECT_KEY_FILE, source_app_name)
    if not source_app:
        return
    source_db = firestore.client(app=source_app)

    # --- Initialize Target Firebase App or Emulator ---
    target_app_name = "hate-crime-tracker-dev"
    target_db = None
    target_app = None # Initialize target_app to None

    if TARGET_TYPE.upper() == "CLOUD":
        print(f"\nConfiguring target: Google Cloud Firebase Project")
        target_app = initialize_app(TARGET_PROJECT_KEY_FILE, target_app_name)
        if not target_app:
            if source_app: firebase_admin.delete_app(source_app)
            return
        target_db = firestore.client(app=target_app)
    elif TARGET_TYPE.upper() == "EMULATOR":
        print(f"\nConfiguring target: Local Firebase Emulator")
        emulator_host = os.getenv("FIRESTORE_EMULATOR_HOST")
        if not emulator_host:
            print(f"FIRESTORE_EMULATOR_HOST environment variable not set. Using configured EMULATOR_HOST_OVERRIDE: '{EMULATOR_HOST_OVERRIDE}'")
            if not EMULATOR_HOST_OVERRIDE:
                print("EMULATOR_HOST_OVERRIDE is not set either. Please configure it or set FIRESTORE_EMULATOR_HOST.")
                if source_app: firebase_admin.delete_app(source_app)
                return
            os.environ["FIRESTORE_EMULATOR_HOST"] = EMULATOR_HOST_OVERRIDE
        else:
            print(f"Using FIRESTORE_EMULATOR_HOST from environment: {emulator_host}")

        print(f"Using dummy key file for emulator: '{EMULATOR_DUMMY_KEY_FILE}' and project ID: '{EMULATOR_PROJECT_ID}'")
        target_app = initialize_app(EMULATOR_DUMMY_KEY_FILE, target_app_name, project_id=EMULATOR_PROJECT_ID)
        if not target_app:
            if source_app: firebase_admin.delete_app(source_app)
            return
        target_db = firestore.client(app=target_app)
    else:
        print(f"Invalid TARGET_TYPE: '{TARGET_TYPE}'. Choose 'CLOUD' or 'EMULATOR'.")
        if source_app: firebase_admin.delete_app(source_app)
        return

    if source_db and target_db:
        copy_collection(source_db, target_db, SOURCE_COLLECTION_NAME, TARGET_COLLECTION_NAME, batch_size=BATCH_WRITE_SIZE)

    # Clean up Firebase apps
    try:
        if source_app:
            firebase_admin.delete_app(source_app)
            print(f"\nFirebase app '{source_app_name}' deleted.")
    except Exception as e:
        print(f"Error deleting source app: {e}")

    try:
        if target_app:
            firebase_admin.delete_app(target_app)
            print(f"Firebase app '{target_app_name}' deleted.")
    except Exception as e:
        print(f"Error deleting target app: {e}")

if __name__ == "__main__":
    main()

