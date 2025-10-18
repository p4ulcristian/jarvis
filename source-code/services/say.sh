#!/bin/bash
# Usage: ./say.sh "text to speak" "feeling/emotion"
# Example: ./say.sh "Hello!" "excited and cheerful"

TEXT="$1"
FEELING="${2:-}"

# Generate speech using OpenAI TTS API
# Use a unique filename that won't conflict
TEMP_FILE="/tmp/say_$(date +%s%N).mp3"

# Use jq to properly escape JSON (handles quotes, newlines, special chars)
# If feeling is provided, prepend it to the text for expressive delivery
if [ -n "$FEELING" ]; then
  EXPRESSIVE_TEXT="[${FEELING}] ${TEXT}"
  JSON_PAYLOAD=$(jq -n --arg text "$EXPRESSIVE_TEXT" '{model: "tts-1", input: $text, voice: "nova"}')
else
  JSON_PAYLOAD=$(jq -n --arg text "$TEXT" '{model: "tts-1", input: $text, voice: "nova"}')
fi

curl -s -X POST https://api.openai.com/v1/audio/speech \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$JSON_PAYLOAD" \
  --output "$TEMP_FILE"

# Check if API call succeeded
if [ ! -f "$TEMP_FILE" ] || [ ! -s "$TEMP_FILE" ]; then
  echo "Failed to generate speech" >&2
  exit 1
fi

# Play the audio and clean up (blocking - waits for playback to finish)
mpv --no-video --really-quiet --volume=90 "$TEMP_FILE" 2>/dev/null

# Clean up after playback completes
rm -f "$TEMP_FILE"
