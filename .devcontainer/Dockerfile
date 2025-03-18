FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    nodejs \
    npm \
    openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*

# Install Firebase CLI
RUN npm install -g firebase-tools

# Install Google Cloud SDK
RUN curl -sSL https://sdk.cloud.google.com | bash

# Add Google Cloud SDK to PATH
ENV PATH $PATH:/root/google-cloud-sdk/bin

# Set working directory
WORKDIR /workspace

# Copy requirements.txt (will be mounted from host)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONPATH=/workspace
ENV GOOGLE_APPLICATION_CREDENTIALS=/workspace/hate-crime-tracker-7d52738f7212.json

# Expose ports for Flask and Firebase emulators
EXPOSE 5000 8080 9099 9199 4000

# Set the default command
CMD ["/bin/bash"]

# Create non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Create workspace directory and set ownership
WORKDIR /workspace
RUN chown ${USERNAME}:${USERNAME} /workspace

# Switch to non-root user
USER $USERNAME

# Note: requirements.txt will be mounted from the host
# Python dependencies will be installed by setup.sh 