---
name: popcorn
description: Make presentation media told as a simple story people follow like a cartoon - a narrated story video (product launch, explainer, demo, pitch), carousels of slides for a feed, short animated clips and GIF loops for a README or a landing page, thumbnails and covers, a voice-over for a recording, etc. - with a preview at every step - a storyboard of real frames, a fast draft, then the final. Use when asked for a promo, explainer or demo video, a video or a carousel for a social feed, an animated hook or GIF, a slide-style video, a thumbnail or cover, or a voice-over. Not for a slide deck or a document to present or read as a file (PPTX, a report, etc.); a feed carousel delivered as a PDF, and a video made from an existing deck, are in scope.
---

# Popcorn

The aim: a piece (a video, a carousel, a loop, a still, etc.) told as a simple story the viewer follows like a cartoon, understood at a glance and followed to the end, made in a few short rounds with the user instead of many slow re-renders. Each round puts something real in front of the user to react to: frames before motion, a cheap draft before the expensive render.

Every answer to the user follows [references/user-output.md](references/user-output.md) (fast to scan, visual-first); read it before the first answer in a task.

## How to use this skill

- **Hard rules** (marked) are followed as written. They protect the user's explicit decisions, honesty and correctness.
- **Directions** are everything else. A good piece depends on its audience, product and platform: use the directions and their challenge questions to decide, and try the idea on a frame before arguing for it. Examples show the kind of thinking expected; they are not a template to copy.
- **The product** here is whatever the piece presents: an app, a game, a service, a physical product, a course, an idea, an event, etc.

## Files

Read each file in full, one file per call, when its stage comes:

| When | Read |
| --- | --- |
| Where it plays (from the brief on), the story, any scene or slide, a clip, a carousel, a thumbnail, the text that goes with it | [references/craft.md](references/craft.md) |
| Voice, sound effects, music, the mix, from the brief on when the piece has sound | [references/sound-voice.md](references/sound-voice.md) |
| Building: scene pages, recordings, `plan.json`, the commands, speed, the checks | [references/toolkit.md](references/toolkit.md) |
| Every answer to the user | [references/user-output.md](references/user-output.md) |

The toolkit (`scripts/`) renders scene pages frame by frame in headless browsers, and plays real recordings inside them, so every preview shows the piece's real look, and the same plan gives the storyboard, the draft and the final.

## Pipeline

The stages run in this order. Each ends with something the user sees.

1. [VID-BRIEF] **Brief.** Settle before drawing anything:
   - **The kind of piece** ([CR-KIND]): marketing (sells the idea, with abstract pictures or real footage and a few large words) or a real presentation (the product as it is). The form: a narrated video, a loop, a carousel, a still, a voice-over, etc.
   - **Who watches and where:** the platform, its shape and length, a file-size cap, whether it plays muted, what it shows before anyone presses play or swipes ([CR-FEED], [CR-CAROUSEL]), the one thing the viewer should leave with (the promise the opening makes, [CR-ONE-MESSAGE]), and the action at the end.
   - **The facts:** what the product really does, from its docs, its code, its footage or the user. Pick the running example the whole piece will follow ([CR-ONE-CASE]).
   - **What only the user can give:** the presenter (photo, name, role), links, whose voice, the music source, brand marks, the product's own photos, footage or access, etc. Ask for all of it at once, with a recommended option for each. Build meanwhile with clearly marked placeholders; never invent the missing piece.
   - **Whether this machine can render** (the toolkit's needs): put any install it lacks into the same message ([VID-ASK-INSTALL]).
   - Challenge: would a viewer who saw only the first seconds know why to keep watching? If not, bring the pain or the promise into them. What would make this read as "one more average tool"? Name it, and cut it from the opening.
2. [VID-STORY] **Story.** Write the script as a table: scene · on screen · voice · rough length ([CR-STORY]). A short loop has the same spine in one breath ([CR-CLIP]). When the story itself is in doubt, this table is the cheap first check; otherwise it goes straight into the storyboard.
3. [VID-BOARD] **Storyboard → the user's yes** ([VID-GATES]). Build the scenes and render the storyboard ([references/toolkit.md](references/toolkit.md)): the key moments of every scene, its beats (single actions or events on screen) left to right, what happens on screen, its voice lines, its length, and whether it is new, changed or kept. Look at every page yourself first ([CR-FINISH], [CR-ONE-CASE]). A feed piece's cover is approved here too, as a still ([VID-GATES], [CR-FEED]): the storyboard shows the plan's cover first, and its feed-size sheet (`scripts/feedsize.py`) goes with it. Voice samples can go to the user together with it ([VID-SOUND]). Later rounds show only the scenes that changed.
4. [VID-SOUND] **Voice and sound** (when the piece has sound; [references/sound-voice.md](references/sound-voice.md)). The user picks the voice by ear from samples ([SV-PICK]). A change of sound effects gets a short listening sample on the same moments before anything re-renders ([SV-SAMPLE]). The lines are recorded from the approved text; scenes render without them, and their lengths decide where each line sits and whether a scene is long enough for its line.
5. [VID-DRAFT] **Draft → the user's yes** ([VID-GATES]). A fast render with the voice and the sound, to judge rhythm, timing and sound: 480p for a video, the loop itself at a small size for a GIF (at fewer frames a second: its smoothness is judged on the final, and the message says so). Before sending it, read the build's warnings, look at its sheet of frames around every transition where the build makes one, and fix what you find ([VID-LOOK]). Send it with its length, its size, what is still a placeholder, and what to listen for.
6. [VID-FINAL] **Final.** Only after the draft is approved: the full-quality render, the same checks on the final file, then delivery: the files with their paths, length and size; how to upload them where they will play (a custom thumbnail, size limits, etc.); the placeholders still open; the files made along the way ([VID-KEEP]). Before it goes out, open every link the piece and its text carry, QR codes included ([CR-PRESENTER]): each opens what it promises. One that doesn't yet (a page not published, a shop listing not live, etc.) is named in the delivery as what blocks posting; one you can't open (behind a sign-in, no network, etc.) is named as unchecked. Companion pieces the user asks for (a thumbnail, the post text, etc.) follow [CR-THUMB] and [CR-POST].
7. [VID-ROUND] **A feedback round**, at any stage:
   - **Find each flagged moment in the build before planning.** The build's timeline maps a timestamp to its scene, voice line and sound cue; look at the frames there. Name the cause, not a guess: which sound plays at that second, which slide shows through the scene change.
   - **Look for the same flaw elsewhere** (the same sound at another scene change, the same leak at another transition, etc.) and fix it in the same round. Where it sits in a scene the user liked, name that scene and what changes in it.
   - **Keep what the user liked untouched,** and say so.
   - **Merging versions:** when the user likes parts of two versions, show the merged piece as a table, each scene with the version it comes from and why. The build keeps earlier versions in `out/old/`.
   - **Another version of the same piece** (with or without a part, another take of a line, etc.) is a variant of the same plan ([references/toolkit.md](references/toolkit.md)): the scenes both share render once, and both versions stay.
   - **Feedback about how a published piece did** (many views and few reactions, people leaving early, etc.): ask, in the same message as the proposed change, for the platform's numbers that show where viewers left (average watch time, etc.). Without waiting for them, check the opening against [CR-FEED] and [CR-CAROUSEL] and the text against [CR-POST] before changing the story.
   - **Then the preview the change needs,** for the changed part only ([VID-GATES]).
   - **Feedback about how the whole reads** (chaotic, slow, repetitive, "average", etc.) is about structure and pace first ([CR-STORY], [CR-PACE]). Effects come after.

## Hard rules

- [VID-GATES] **Previews before the final, each with the user's yes before the next** (the user's own process).
  - A piece that moves (a video, a loop, etc.):
    1. a storyboard of static frames;
    2. a fast draft (480p for a video; the loop itself at a small size for a GIF);
    3. the final render.
  - A still (a thumbnail, a cover, a carousel's slides, etc.): the still itself at the size people first see it (a phone's width for a carousel), its variants side by side where there are several ([CR-THUMB]), then the finished file.
  - A voice-over for existing footage: voice samples (unless the voice is the user's own recording or a placeholder, [SV-PICK]), then the narration over a low-resolution copy of the footage, then the final mix.

  The user may skip a gate by saying so; the skip holds for the rest of the task unless they say otherwise. A change after a gate goes back to the earliest preview that would show it, for the changed part only: a new or redesigned scene to its slides, a sound change to a sound sample ([SV-SAMPLE]), a timing change to a draft. From there it goes on to where the work stood, through no other preview, except that a change in what moves or sounds is seen in a draft of the changed part before the final (a sound sample already heard counts as that draft).
- [VID-REAL-FRAMES] **Storyboard frames are the piece's own frames:** rendered from its scene pages, or stills of the real product or footage the piece will use, in its own look. Wireframes, sketches or mockups never stand in for them: the user approves what the piece will show. When nothing can be rendered (an install the user declined), the script table ([VID-STORY]) is the preview, said as such, and the work waits there for the user's decision.
- [VID-HONEST] **Nothing invented.**
  - No made-up numbers, results, quotes or testimonials; every claim about the product is checked against the product.
  - A staged picture that could be taken for the real product or a real result is labelled as an illustration where the piece is published; a real presentation shows the real product ([CR-KIND]).
  - Other companies' logos and interfaces are not imitated: name them in plain text instead.
- [VID-VOICE-ID] **A voice presented as a real person's is one they gave or chose:** their recording, a clone of their own recording made with their consent, or a voice they picked for their own piece. Until then every report says the voice is a placeholder, and the published piece doesn't present it as theirs.
- [VID-ASK-INSTALL] **Downloads, installs and paid services need the user's yes** (a TTS model, ffmpeg, a package, etc.): say what, how big and why. API keys and accounts are the user's to enter.
- [VID-LOOK] **Look before you claim** (Visual honesty in [references/user-output.md](references/user-output.md)). Before a draft or a final goes out, check its warnings, and its transitions sheet where the build makes one. The agent can't hear: measure what can be measured (loudness, overlaps, pace, clipping), and leave the judgement by ear to the user, saying so.
- [VID-KEEP] **Renders, samples and check files you made stay.** List them at the end; the user removes them.
