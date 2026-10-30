# HarmonyKit sample credits and licenses

HarmonyKit plays real recorded instruments only. There are no oscillators, noise generators or synth stand-ins anywhere, including the click.

## Melodic instruments: FluidR3 GM SoundFont (MIT), MP3 renders by gleitz/midi-js-soundfonts (MIT)
Loaded at runtime from jsDelivr, pinned to commit `044fab8e1456bfafc5776e86dfd6bb8697149aef` (never @main or @gh-pages):
`https://cdn.jsdelivr.net/gh/gleitz/midi-js-soundfonts@044fab8e1456bfafc5776e86dfd6bb8697149aef/FluidR3_GM/<instrument>-mp3/<note>.mp3`
If jsDelivr refuses a file, the app falls back to raw.githubusercontent.com at the same commit.

Instruments used: choir_aahs (harmony guide voices), voice_oohs (ooh pads and guide voices), acoustic_grand_piano, electric_piano_1, electric_bass_finger, string_ensemble_1, acoustic_guitar_nylon, flute, clarinet.
There is one sample every 4 semitones per instrument, so playback pitch shift is at most ±2 semitones. The engine refuses anything beyond ±4.

FluidR3_GM.sf2 by Frank Wen and contributors, MIT License.
midi-js-soundfonts © Benjamin Gleitzman, MIT License: https://github.com/gleitz/midi-js-soundfonts/blob/044fab8e1456bfafc5776e86dfd6bb8697149aef/LICENSE.txt

## Acoustic drum kit + click: Virtuosity Drums (CC0 1.0), bundled in `samples/drums/`
sfzinstruments/virtuosity_drums @ `9f04cf9a734527edfbb0a4eee1f674e45bbf71bc`. License: CC0 1.0 Universal, https://creativecommons.org/publicdomain/zero/1.0/
kick, snare, ghost (mid_snare_center_vl4), rim (mid_snare_crossstick_vl10, also used as the metronome click), hat, ohat (mid_hh_open_vl3_rr1).
Trimmed with a 120 ms fade-out, stored as 48 kHz 16-bit FLAC.

## Demo melody
"Ode to Joy" (Ludwig van Beethoven, Symphony No. 9, 1824), public domain. Entered as notes; the lead plays on the sampled clarinet and its harmony parts on the sampled choir.
