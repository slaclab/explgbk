#!/bin/bash
set -e

echo "Starting MongoDB restore from /dumps directory..."
for file in /dumps/*.gz; do
    if [ -f "$file" ]; then
        echo "Restoring $file..."
        mongorestore --archive="$file" --gzip
    fi
done
echo "MongoDB restore completed."
