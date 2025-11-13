#!/bin/bash
QUERY="$*"

echo "Pošiljam JSON: {\"chatInput\": \"$QUERY\"}"

RESPONSE=$(curl -s -X POST "http://localhost:5678/webhook/7bd4c9f4-7afc-40a7-8ef7-fe224f20550b/chat" \
  -H "Content-Type: application/json" \
  -d "{\"chatInput\": \"$QUERY\"}")

echo -e "\n🤖 AI: $RESPONSE\n"
