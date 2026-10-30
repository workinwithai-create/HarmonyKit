#!/usr/bin/env bash
# Proves HarmonyKit has no synthesized sound sources: no oscillators, no noise buffers, no generated tones, no random numbers.
# Usage: qa/no_synth.sh [live-url]
set -u; fail=0
pat='createOscillator|OscillatorNode|PeriodicWave|createPeriodicWave|createConstantSource|ConstantSourceNode|Math\.random'
echo "== repo (app.js, index.html) =="; if rg -n "$pat" app.js index.html; then fail=1; else echo "none"; fi
echo "== every createBuffer( in app.js (must only be filled from recorded/imported voice audio) =="; rg -n -o "createBuffer\(.{0,90}" app.js
echo "== every sound source: createBufferSource( count, and the sample sources it plays =="; rg -c "createBufferSource\(" app.js; rg -n -o 'SF_SHA = "[0-9a-f]+"|samples/drums/[a-z]+\.flac|`samples/drums/\$\{[a-z]+\}\.flac`' app.js | head
if [ -n "${1:-}" ]; then echo "== live $1/app.js and $1/index.html =="; if (curl -s "$1/app.js"; curl -s "$1/") | rg -n "$pat"; then fail=1; else echo "none"; fi; fi
[ $fail = 0 ] && echo "PASS: no synth sound sources" || echo "FAIL"; exit $fail
