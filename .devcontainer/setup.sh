#!/bin/bash

# Create Python virtual environment
python -m venv env
source env/bin/activate

# Add virtual environment activation to .bashrc
echo "source /workspace/env/bin/activate" >> ~/.bashrc

# Install project dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Check for credentials file
if [ ! -f "./hate-crime-tracker-7d52738f7212.json" ]; then
    echo "⚠️  Please add your Google Cloud credentials file (hate-crime-tracker-7d52738f7212.json)"
    echo "Don't have the credential file?"
    echo "1. Open the tracker project in Firebase Console."
    echo "2. Click the gear icon (⚙️) near the top-left corner and select 'Project settings'."
    echo "3. Navigate to the 'Service accounts' tab."
    echo "4. Click the 'Create new private key' button."
    echo "5. Download the JSON file and paste it in the root directory of this project."
    echo "If you couldn't find it, please ask Jahong for help."
fi

echo "Development environment setup complete"
echo "To start the development server:"
echo "1. Login to Firebase: firebase login"
echo "2. Start Firebase emulators: firebase emulators:start"
echo "3. In a new terminal: python main.py"