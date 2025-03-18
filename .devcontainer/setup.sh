#!/bin/bash

# Create Python virtual environment
python -m venv env
source env/bin/activate

# Add virtual environment activation to .bashrc
echo "source /workspace/env/bin/activate" >> ~/.bashrc

# Install project dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Firebase CLI if not already installed
if ! command -v firebase &> /dev/null; then
    curl -sL https://firebase.tools | bash
fi

# Check for credentials file
if [ ! -f "./hate-crime-tracker-7d52738f7212.json" ]; then
    echo "⚠️  Please add your Google Cloud credentials file (hate-crime-tracker-7d52738f7212.json)"
    echo "You can do this by:"
    echo "1. Opening the file in GitHub Codespaces"
    echo "2. Creating a new file named 'hate-crime-tracker-7d52738f7212.json'"
    echo "3. Pasting your credentials"
fi

# Check for firebase.json
if [ ! -f "./firebase.json" ]; then
    echo "⚠️  Please add your firebase.json file"
    echo "You can do this by:"
    echo "1. Opening the file in GitHub Codespaces"
    echo "2. Creating a new file named 'firebase.json'"
    echo "3. Pasting the following content:"
    echo '{
 "emulators": {
   "functions": {
     "port": 5001
   },
   "ui": {
     "enabled": true
   },
   "singleProjectMode": true,
   "firestore": {
     "port": 8080
   },
   "storage": {
     "port": 9199
   }
 },
 "storage": {
   "rules": "storage.rules"
 }
}'
fi

# Check for storage.rules
if [ ! -f "./storage.rules" ]; then
    echo "⚠️  Please add your storage.rules file"
    echo "You can do this by:"
    echo "1. Opening the file in GitHub Codespaces"
    echo "2. Creating a new file named 'storage.rules'"
    echo "3. Pasting the following content:"
    echo 'rules_version = '\''2'\'';
service cloud.firestore {
 match /databases/{database}/documents {
   match /{document=**} {
     allow read, write: if true;
   }
}'
fi

echo "Development environment setup complete"
echo "To start the development server:"
echo "1. Login to Firebase: firebase login"
echo "2. Start Firebase emulator: firebase emulators:start"
echo "3. In a new terminal: python main.py"