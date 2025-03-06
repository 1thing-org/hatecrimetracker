#!/bin/bash

# Create Python virtual environment
python -m venv env
source env/bin/activate

# Install project dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Initialize Firebase project
echo "Attempting Firebase login..."
if ! firebase login --no-localhost; then
    echo "⚠️  Firebase login failed. Please try again manually after container setup."
fi

# Check for credentials file
if [ ! -f "./hate-crime-tracker-7d52738f7212.json" ]; then
    echo "⚠️  Please add your Google Cloud credentials file (hate-crime-tracker-7d52738f7212.json)"
    echo "You can do this by:"
    echo "1. Opening the file in GitHub Codespaces"
    echo "2. Creating a new file named 'hate-crime-tracker-7d52738f7212.json'"
    echo "3. Pasting your credentials"
fi

echo "Development environment setup complete"
echo "To start the development server:"
echo "1. Start Firebase emulator: firebase emulators:start"
echo "2. In a new terminal: python main.py"