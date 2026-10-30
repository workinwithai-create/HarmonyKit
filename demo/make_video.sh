#!/usr/bin/env bash
# Trims the screen capture to the moment Play was pressed and lays the app's exported WAV under it. Captions only: no voice-over, no generated audio.
set -euo pipefail; cd "$(dirname "$0")"
V=$(python3 -c "import json;print(json.load(open('marks.json'))['video'])"); P=$(python3 -c "import json;print(json.load(open('marks.json'))['play'])"); A=$(python3 -c "import json;print(json.load(open('marks.json'))['wav'])")
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf; OUT=${1:-harmonykit-demo.mp4}
cap(){ echo "drawtext=fontfile=$FONT:text='$1':fontsize=34:fontcolor=white:box=1:boxcolor=0x0e1013cc:boxborderw=14:x=(w-text_w)/2:y=h-92:enable='between(t,$2,$3)'"; }
VF="$(cap 'Cannot figure out the harmonies?' 0 3.4),$(cap 'Bring your lead + chords. HarmonyKit writes the parts.' 3.4 7.6),$(cap '3rd above, low part, ooh pad: singable, no rubs' 7.6 11.8),$(cap 'Learn each part solo, sing it, get scored per bar' 11.8 15.6),$(cap 'Real choir samples. WAV, MIDI, harmony sheet, stems.' 15.6 18.4),$(cap 'harmonykit.vercel.app  -  \$19 once' 18.4 21)"
ffmpeg -loglevel error -y -ss "$P" -i "$V" -i "$A" -t 20.8 -map 0:v -map 1:a -af "adelay=110|110" -vf "$VF,format=yuv420p" -r 30 -c:v libx264 -crf 20 -preset medium -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"
ffprobe -v error -show_entries stream=codec_type,codec_name,duration -of compact "$OUT"
