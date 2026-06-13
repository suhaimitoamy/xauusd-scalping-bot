#!/bin/bash
mkdir -p data logs
touch data/.gitkeep logs/.gitkeep
zip -r xauusd-scalping-bot-final.zip . -x "*.git*" "*.env" "data/*.sqlite" "logs/*.log" "*__pycache__*" "*.pyc" "pack.sh"
echo "Package xauusd-scalping-bot-final.zip created successfully."
