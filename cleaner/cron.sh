#!/bin/bash

PROJECT_DIR="/wdata/nexus/cleaner_nexus"
PYTHON="$PROJECT_DIR/.venv/bin/python"
SCRIPT="$PROJECT_DIR/cleaner.py"
CONFIG_DIR="$PROJECT_DIR/config"
LOG_FILE="$PROJECT_DIR/cron.log"

for config in "$CONFIG_DIR"/*.yaml; do
    echo "[$(date)] Запуск с конфигом: $config" >> "$LOG_FILE"
    "$PYTHON" "$SCRIPT" --config "$config" >> "$LOG_FILE" 2>&1
done


chmod +x /wdata/nexus/cleaner_nexus/run_cleaner.sh
