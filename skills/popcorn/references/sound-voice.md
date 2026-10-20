# Sound and voice

Directions for the voice, the sound effects, the music and the mix. The agent can't hear the result: everything here pairs a choice the user makes by ear with the checks the agent can measure ([VID-LOOK]).

## Voice

- [SV-PICK] **The user picks the voice by ear, from samples of the same text.** Protects: a voice the user is happy to put their name under; a description of a voice says little.
  - Make samples from different engines, not only different voices of one engine: engines differ more than their voices do. Label each sample with its engine and voice so the pick can be repeated.
  - The kinds of source, as examples: a local text-to-speech model (open ones, with or without voice cloning; the strongest change fast, so look up the current ones), the system's built-in voices, a cloud service with the user's own key, the user's own recording, etc. The system voices are usually the weakest.
  - Start from what is already installed; each further engine is a download with its own yes ([VID-ASK-INSTALL]): say its size, keep it in a folder of its own, and say where it went.
  - Note what comes with a voice: its licence, and any watermark the engine embeds in its audio.
  - When the user asks for better than all the samples, look for a stronger engine rather than tuning the same one.
  - A placeholder voice (one the presenter's own will replace) needs no round of samples: use what is at hand, and say it is a placeholder.
- [SV-OWN] **The presenter's own voice, when the piece speaks as them** ([VID-VOICE-ID]). Protects: a first-person piece that sounds like the person in it.
  - Two routes: they record the script themselves (most alive, but every edit means a new recording), or they record a short sample of free speech and a cloning engine speaks the script in their voice (edits stay cheap). Recommend one with its trade-off.
  - A recording is easiest one file per line. One long take is cut at its pauses first (ffmpeg's `silencedetect` finds them), and the pieces are matched to the lines by listening, or with a speech recogniser where one is available.
  - Until their voice exists, the draft uses a placeholder voice and says so.
- [SV-WRITE] **Write the narration for the ear.** Protects: lines a voice can say naturally and an engine can say right.
  - Plain and short, one idea per sentence ([CR-WORDS]).
  - Spell what the engine misreads: initials as letters ("A.I."), product names by sound, numbers as words where it stumbles, etc.
  - One line per beat, so a line can be re-recorded or moved alone.
- [SV-TAKES] **Check every take before it goes in.** Protects: a line that silently loses its end.
  - Text-to-speech engines sometimes drop the end of a line; such a take is too short for its words. `voice_prep.py` measures each take's pace (words per second), skips a take far faster than the line's other takes, and flags a line far faster than the others: listen to it, or make more takes and keep the full one. On a person's own recording the flag can fire on a quick speaker: listen before retaking.
  - Where a speech recogniser is available, read each line back and compare it with its text.
  - A model that runs on the GPU slows the frame renderer a lot when both run at once: record the voice before or after rendering, not during.

## Sound effects

- [SV-FX] **Soft, short and tonal, each with a reason.** Protects: the viewer's ears; bright noise is what hurts at video volume.
  - A cue for an event the viewer sees: a click under a click, typing ticks under text that streams in (this works well), two quiet falling notes under a red ✕, a soft chime under a ✓, a soft rising tone under a big move, etc. (the kinds in `scripts/sound.py`).
  - No bright noise: no hiss sweeps or whooshes, no cracks, no buzzers. An impact is low-passed and dull; where the genre wants punch (a trailer, a game, etc.), it stays short and under the voice.
  - A transition gets a very soft cue or none; a cue at every scene change adds up to noise. The build adds none unless the plan names one.
- [SV-SAMPLE] **A sound change is approved on a sample first.** Protects: a render spent on a sound the user then rejects. `sound_sample.py` plays the same moments of the built video with the current sound and with each candidate, labelled on screen; the user picks by ear, then the change goes into the build.

## Music

- [SV-MUSIC] **A track that follows the story and steps back under the voice.** Protects: a mood that carries the story, and a licence that holds.
  - Sources, for example: synthesized by the toolkit (no licence to clear), a track the user owns or has licensed (a library, their own, commissioned, etc.), or none. Never a track whose licence is unknown.
  - Its mood follows the story (example: lighter under the opening, tighter under the problems, warm after the turn). A short breath before a reveal can help; long silence reads as a gap.
  - It ducks under the voice (the build does this).

## The mix

- [SV-MIX] **Measured where it can be, judged by ear where it can't.** Protects: a mix that is loud enough, clean and fair to the voice, without the agent claiming what it can't hear.
  - The build normalizes loudness to the plan's target (the platform's own; web video is commonly around −16 LUFS integrated) and reports what it measured; the voice sits on top; nothing clips.
  - The build's warnings about the voice lines are fixed before the draft goes out ([VID-DRAFT]).
  - What can't be measured (whether a sound is pleasant, whether the music is too loud for taste, whether the voice sounds natural) goes to the user, said plainly as "for your ear".
