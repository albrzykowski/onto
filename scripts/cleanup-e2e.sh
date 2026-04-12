#!/bin/bash
set -e

echo "Cleaning environment..."

# Clean PostgreSQL tables
echo "Cleaning PostgreSQL..."
PGPASSWORD=postgres psql -h postgres -U postgres -d onto -c "
  TRUNCATE relations, entities CASCADE;
"

# Clean Qdrant collections
echo "Cleaning Qdrant..."
curl -s -X DELETE "http://qdrant:6333/collections/entities" || true

# Clean Pulsar topics
echo "Cleaning Pulsar topics..."
curl -s -X DELETE "http://pulsar:8080/admin/v2/namespaces/public/default" || true

echo "Environment cleaned."