# HarmonyKit

**Can't figure out the harmonies? Bring your lead and your chords.** HarmonyKit writes singable harmony parts for your melody, plays each one alone on real choir samples so you can learn it, then scores every take you sing, bar by bar.

Live: https://harmonykit.vercel.app · by WorkinWithAI

## What it does
1. **Your song**: BPM, key and chords (one per bar). Your own BPM, key and chords always win; "Suggest from my lead" only fills the box when you ask.
2. **Your lead**: sing it into the mic, play it on a MIDI keyboard (velocity + sustain pedal; notes never start the transport), import a voice memo (WAV/MP3/M4A, transcribed) or a MIDI file, or load the demo (Ode to Joy, public domain). Every full loop pass is a take; a partial pass is kept when you stop, seek or hide the tab.
3. **Harmony parts**: pick a stack (Duet, Trio, Country, Oohs, Full stack) or set each of the 3 parts yourself (3rd above, 3rd below, 6th below, low part, octave, ooh pad). A Viterbi writer chooses the most singable path: chord tones on strong beats, nothing a 2nd/7th/tritone against the lead, small leaps, no parallel 5ths/octaves. Click any note to move it a step or lock it; the rest of the line re-routes around your edits.
4. **Learn and sing**: 🎧 solos one part's guide (choir aahs / voice oohs, FluidR3) with the lead and band. ● Sing this part records one take per pass (guide in headphones or off to test yourself) and scores it: pitch within 50 cents (octave-free) and coverage, per bar.
5. **Listen**: A = Thin (lead + band, harmonies muted) vs B = Need (full stack), loudness-matched. Audio output select (setSinkId with fallback), MIDI out mirrors every part on its own channel.
6. **Export**: `harmonykit-<stack>-<bpm>bpm-<key>.wav` (48 kHz / 24-bit, exact loop length, downbeat at sample 0, peak −1 dBFS), `.mid` (one track per written harmony line + lead + band + takes, chord marker per bar), a harmony sheet (.txt, note names per bar) and a stems ZIP (every part, guide and take, plus raw sung audio). iPhone: share sheet → Save to Files, with a tap-to-save fallback.

## Sounds
Real samples only: FluidR3 GM (MIT) pinned to commit `044fab8e1456bfafc5776e86dfd6bb8697149aef` (choir aahs, voice oohs, piano, e-piano, finger bass, strings, nylon, flute, clarinet) and the bundled CC0 Virtuosity acoustic kit (the click is its cross-stick). No oscillators, noise or generated tones anywhere (`qa/no_synth.sh`).

## Pricing and where to sell
- **Recommend: $19 one-time.** It's a per-song writing/learning utility with no server cost per user (everything runs in the browser, takes stay in IndexedDB), and songwriters push back on subscriptions for small single-purpose tools. Same price point as UnderKit, so a bundle later is easy.
- **Sell on Lemon Squeezy** (preferred): merchant of record handles VAT/sales tax worldwide, has a license-key API the app's gate already speaks, and the checkout overlay works on a static Vercel site. Gumroad is the fallback for one-time digital sales; Bandcamp only if it ships bundled with sample/vocal packs.
- The gate in `app.js` (`LEMON = { checkoutUrl, storeId, productId, price }`) only unlocks keys whose `store_id`/`product_id` match. With an empty config the buy button reads "Checkout opening soon" and every export is free. When configured: 8-bar WAV/MIDI/sheet stay free; 16-bar renders and stems need a key.

## Files
- `index.html`, `styles.css`, `app.js`: the whole app (static, no build step beyond copying into `dist/`).
- `public/samples/`: bundled CC0 kit + `CREDITS.md`.
- `qa/s9.py`: AUDIO-ENGINE-RULES §9 checks (c1–c7) + product checks · `qa/export_test.py`: WebKit iPhone 13 + Chromium export test · `qa/record_test.py`: sing-a-part recording + scoring · `qa/no_synth.sh`.
- `demo/`: screen-capture + exported-audio demo video scripts.

No auth, no database, no analytics. MIT licensed (code); sample licenses in `public/samples/CREDITS.md`.
