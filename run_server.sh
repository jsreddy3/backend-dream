#!/bin/bash

# Load environment variables from .env file
export $(grep -v '^#' .env | xargs)

# Print the OpenAI API key (masked for security)
echo "Using OpenAI API Key: ${OPENAI_API_KEY:0:10}...${OPENAI_API_KEY: -4}"

# Run the server
uvicorn new_backend_ruminate.main:app --reload --host 0.0.0.0 --port 8001