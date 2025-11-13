#!/bin/bash

# Preveri, ali je podan parameter
if [ -z "$1" ]; then
  echo "Uporaba: $0 'tvoje vprašanje'"
  exit 1
fi

QUESTION="$1"

# URL tvojega webhooka
WEBHOOK_URL="http://localhost:5678/webhook/9caea900-2abe-46f6-bf3e-8ef6d2d54e17"

# Pošlji POST zahtevo in počakaj na odgovor
RESPONSE=$(curl -s -X GET "$WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -d "[{\"body\":{\"chatInput\":\"$QUESTION\"}}]")
# Izpiši celoten JSON odgovor
echo "$RESPONSE"
