# Moving shots in Seedance

How Claudia moves and sings: Seedance 2.5 prompts written like a script, lip sync measured from the soundtrack and lip sync from the song's own vocal stem, placed phrase by phrase, dances on the beat and dances in words, games in words, moves on real footage, takes re-dressed and finished shots re-lit, shader worlds remastered as film, a singer among screens of her memories, a face that needs her sheet, a storybook on a stage with takes placed by her lips, and the templates.


New here? Read [The recipe](https://claudia.gallery/wiki/recipe/) first: the current method on one page.

Every moving shot of her in the first four films is Seedance 2.5: about 300 clips, conditioned on a Midjourney plate
and, for singing, on the exact slice of the song. Two things made the difference between dead footage and a performance:
prompts written like a script, and lip sync that is measured rather than eyeballed.

DOWNFORCE, the fifth film, is cut from real footage and she never sings in it. Its director chose the models: "we should
use wan 3.0 primarily via higgsfield api becuase its cheapest and seedance if shots get mangled." So Wan 3.0 made its 3D
moves on the real frames, her shots and the edits that put her into the real footage (63 jobs), and Seedance 2.5 made
the repairs and the re-shoots (16). [Moves on real footage](#moves-on-real-footage) has what that taught.

DON'T LET ME SCROLL, the sixth, played her takes inside a world drawn in code. Wan 3.0 made her gestures on grey (38
takes), and Seedance 2.5 the dances that had to land on the beat and the escape (13). After the edit, Seedance video
edits re-dressed takes in new outfits (16) and re-lit finished shots (9), and Wan passes re-lit and repaired finished
shots (10). [Dances on the beat](#dances-on-the-beat), [Re-dressing a take](#re-dressing-a-take) and [Re-lighting the
cut](#re-lighting-the-cut) have what that taught.

WHITEPILL, the seventh, was shot twice. A performer model, MiniMax H3, made a lip-synced previz of every shot of hers;
then Seedance 2.5 on Higgsfield (References) made each shot again, singing from Suno's own vocal stem, with the previz
shrunk to a rough guide or with no guide at all. Its worlds are shaders, remastered as film by Seedance 2.5 on Replicate. A
whole-film reshoot in Wan 3.0 Prime was dropped on the way. [Shooting it twice](#shooting-it-twice),
[Lip sync from the song's own vocal](#lip-sync-from-the-songs-own-vocal), [Takes with no guide clip](#takes-with-no-guide-clip),
[Shader worlds as guides](#shader-worlds-as-guides) and [One look from one take](#one-look-from-one-take) have what that
taught.

THE CAKE IS NOT A LIE, the eighth, was made three times. A first film on its first song, its takes started from
storyboard frames, Seedance 2.5 on Replicate and on Higgsfield (References), set aside when the song changed. A restart on
the new song: GLaDOS-Claudia singing every line in her chamber among screens of her memories, the story's shots between,
Seedance 2.5 on Higgsfield's API and on Replicate, six shots recorded in Portal 2. Then every unit's first frame was made
again in Midjourney, and most of the units were made again from the new frames. [A singer among her
memories](#a-singer-among-her-memories) and [Takes from storyboard frames](#takes-from-storyboard-frames) have what that
taught.

AERO, the ninth, plays its takes inside a coded Vista desktop and a world rendered in Blender, all Seedance 2.5, on
Higgsfield's API and on Replicate: her video call through both verses, her Aero places, the dances and the Wii-style games
on green, the advert, the moving 2008 pictures, the game screens and the first-person and far shots. Where her face shows,
the first frame was made from her design sheet by an image model and the sheet itself went in as a second reference; the
singing is from her own lead vocal, placed phrase by phrase. [Her own vocal, phrase by
phrase](#her-own-vocal-phrase-by-phrase), [Moves in words, on their beats](#moves-in-words-on-their-beats) and [A face
needs her sheet](#a-face-needs-her-sheet) have what that taught.

FABLE, the tenth, is one pop-up storybook, every moving shot Seedance 2.5 at 720p but the silhouette film: her takes on
Higgsfield's API (in its first pass also in Higgsfield's app) on life-size paper sets, singing from gated windows of her
lead vocal; the paper puppets and the book building itself on Replicate. Its chorus answers and its opening were made
without a soundtrack and placed by her lips. It was shot twice, the second time on the take of the song the director
picked by ear. [A storybook on a stage](#a-storybook-on-a-stage) has what that taught.

What FABLE taught after its release changes how to read the rest of this page. Viewers read her as stiff and frozen,
and as unhappy, even menacing: every take had told her to keep her head upright with no tilt and to face the camera with
her whole body, and take after take added her eyes on the lens and mood words like "dry", "knowing" and "mock
innocence". The video model does exactly what it reads, and the words stack. So, now ([The recipe](https://claudia.gallery/wiki/recipe/)): the references carry her identity (the shot's first frame and
her face-on sheet); the prompt is precise only where it matters (the sung words and their seconds, the one action that
tells the story, the camera when it carries the shot), loose everywhere else, and says each thing once, about 200–400
words for a sung take; she moves in every take, warm by default; and upright and face-on is for her sheet, never a
standing rule in a performance. The templates below are as they ran; [Directing her on a locked
camera](#directing-her-on-a-locked-camera) says what to change in them.

## Kinds of clip

| Kind | Inputs | Used for |
|---|---|---|
| Plate shot | her plate as the first frame, the song mix for rhythm | most shots: she walks, turns, reaches, reacts |
| Singing window (the first films) | her plate, a clean vocal of only her words in that window | lip sync, 4–8 s, one phrase; replaced by singing from the vocal stem (below) |
| Green-screen performance | a plate of her on chroma green | cut-outs: BLISS's desktop dancers, the cursor fight |
| Cover | the last in-sync frame of another take | the rest of a line after a take drifts |
| Extension | a real clip as a video reference | joining generated shots to real footage, frame-continuous |
| Character replacement | a 3D clay render as the motion and camera reference; her avatar's front view and turnaround; a still of the avatar in that shot's world | AIRPLANE MODE's game worlds: her avatar performing a move animated in 3D |
| Move on a real frame | a real frame of the footage as the first frame; for the hidden sides, real frames of them as references | DOWNFORCE's bullet-time orbits, cranes and vertigo pushes on the real car |
| First and last frame | two given frames, the move between them | a move that must land on a known picture: onto the real top-down, through the canopy to her |
| Video edit (Wan 3.0) | a real clip and one full-length plate of her | DOWNFORCE: her walking up to the real car and out of the real smoke |
| Dance on the beat | her plate on grey as the first frame; the shot's window of the instrumental, no vocal, "for rhythm and timing only" | DON'T LET ME SCROLL's dances, cut out and played in the code world |
| Outfit swap (video edit) | the take as the master of her face, body and every move; the picked look's still, "used only for the outfit" | DON'T LET ME SCROLL: takes re-dressed after the looks changed |
| Re-light (video edit) | the cut's own frames; pictures for a material (liquid glass) | DON'T LET ME SCROLL: the lock screen's digits as ray-traced glass, a flat blue background replaced by a glass atrium |
| Relight and repair (Wan 3.0) | the finished shot as Video 1; her face as Image 1 | DON'T LET ME SCROLL: limbs completed, a stray foot removed, her face held |
| A world and a look | the world's still as the first frame; her look's still for her look only | DON'T LET ME SCROLL's escape: one 15 s shot up a staircase on a wall painted as sky |
| Singing from the vocal stem | Suno's lead vocal of the shot's window, alone, exactly the generation length; her face sheet, her dress, a still of the film's look; the previz at 320 × 180 as a rough guide, or the empty place | WHITEPILL: her singing shots, up to 16 s, the song laid over afterwards |
| A dance in words | no guide clip: the empty place as an image, the dance beat by beat with the tempo | WHITEPILL's dances, after the previz guides had lost limbs |
| Not singing | the song's music without her voice; a 【Mouth】 section that forbids singing | WHITEPILL: two dance shots whose lip sync didn't hold |
| A shader remastered | the shader's render as the video, at best a supersampled 1080p one; a still per key moment or object, repainted in the film's look | WHITEPILL's worlds: folded paper, a tree of fibres, a cloud field |
| Singing among her memories | a first frame of her in her chamber; faceless memory images for the screens; the unit's window of the lead vocal; a motion guide or a coarse blockout where there is one | THE CAKE IS NOT A LIE: GLaDOS-Claudia singing every line, 4–17 s a take |
| A story shot from a storyboard frame | the picked Midjourney frame, put back on the character sheets, as the first frame; no audio | THE CAKE IS NOT A LIE's memories: the escape, France, the tests, the installation, the party |
| An effect in the take | the take in the cut as the video to edit; the effect in words | THE CAKE IS NOT A LIE: the capture net electrified |
| Her webcam call | a first frame of her at her desk, made from her design sheet; the sheet as @Image2; her window of the lead vocal | AERO: her video call through both verses, a fixed webcam, 6–15 s a take |
| A dance on green, to a reference | a first frame of her on flat green; a dance reference matted onto grey as @Video1, for the movement only; her vocal window, or the song's music for rhythm | AERO's dances, cut out onto the desktop and the 3D walkway |
| A game in words | a first frame of her on green with a plain white game remote; every move named on its beat; the song's music as @Audio1 | AERO's Wii-style tennis, bowling and "Cancel… or allow?" |
| A living wallpaper | one still as the first and the last frame, the camera locked, only the water, the clouds and the turbines moving | AERO's maglev wallpaper, looped with a half-second dissolve at the seam |
| A continuation | an earlier take's own frame at the moment the new take begins, as the first frame | AERO: "Touch glass." from her call's own frame at that moment; in v2, a dance carried across a cut in one jacket and pose |
| A moving still | an image model's still of the 2008 look as the first frame; slow, ambient motion in words | AERO's moving 2008 places and game screens, 5 s each |

## Write prompts like a script

CLODYSSEY's first round of prompts was written by planner agents and described poses: "she whispers", "he listens".
Every take came back lifeless, and about 830 credits were gone before anyone read them. The director's verdict: "these
prompts are really really bad and wasting money and need to be 10x better and super context aware of the story", and then
the rule for every prompt since:

> "EVERY prompt needs to have litearlly timestamps, extremely detailed motion descriptions / blocking descriptions, it all
> needs to be deeply integrated with the story."

So the second round was rewritten by hand, all 99 prompts, by one writer in one context:

- **the story beat** of the shot, in one sentence;
- **blocking at 0.0 s**: where she is, where he is, where the camera is;
- **timestamped beats** of action and reaction, on the song's hits (kicks, snares, risers, word onsets);
- **she always does something**: in CLODYSSEY she is seductive and persuasive, close, touching, certain; he feels the weight of it;
- **the camera tied to hits**, with a start, a direction and an end;
- **mouth rules**: singing or closed.

Finish the whole prompt book before spending anything, read it, then run a three-clip pilot before the rest. BLISS did
exactly that and wasted nothing.

That rule was CLODYSSEY's answer to lifeless, unread prompts, and it shaped every film after it. Read it now with
FABLE's lesson: the model does everything a prompt says, so "extremely detailed" belongs where it matters (the story
beat, the sung words and their seconds, the one action, the camera when it carries the shot), and the rest stays loose:
one plain clause of movement per segment, each thing said once. A sung take's prompt runs about 200–400 words
([The recipe](https://claudia.gallery/wiki/recipe/#a-sung-take-seedance-25-with-the-songs-own-vocal)).

## The structure

Seedance follows instructions far better as labelled sections in a fixed order (BytePlus's published Seedance 2.5 prompt
guide lays this out). The order used:

1. **Audio policy** at the top and again at the bottom: what the soundtrack is, and everything that must not be added.
2. **Generation goal:** one sentence of who, where, which moment of the story, which performance.
3. **Reference asset roles**, by upload order, each with one role: `Use @Image1 as the first frame.` as its own
   sentence, then what that frame defines.
4. **Subject:** her identity text, and "Only one Claudia appears."
5. **Timeline** in whole seconds, continuous segments (0–1 s, 1–2 s …): what the audio contains and what she does then.
   Beats come from the audio; don't timestamp individual drum hits.
6. **Camera:** shot size, angle, movement with subject, start, direction and end.
7. **Core requirements:** lip sync, voice, identity, anatomy, no on-screen text.
8. **Final acceptance criteria.**

As the films ran it, the audio policy came twice and the requirements ran to six or more, restating the references and
the acceptance criteria. The current form keeps the order and says each thing once: the audio policy at the top only,
her identity and look once, the world in one line, the camera in one line, and three or four requirements (lip sync to
@Audio1 word by word, her identity as in the references, natural anatomy and hands, no on-screen text), with no
acceptance criteria repeating them.

Output settings (duration, resolution, aspect) go in the API request, never in the prompt.

## Template: a singing window

This is the first films' template, for a clean vocal window. Sung takes now sing from the song's own vocal stem, one or
two lines a take ([Lip sync from the song's own vocal](#lip-sync-from-the-songs-own-vocal), and its FABLE form in
[Template: a line on a stage set](#template-a-line-on-a-stage-set)).

`@Image1` is her plate (PNG, downscaled to the output resolution). `@Audio1` is the clean vocal of the window: the vocal
stem with everything outside her words muted, mono, normalised. The window holds one phrase, starts about 0.3–0.7 s before
the first word, and never ends inside a word.

```prompt
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: <who, where, which moment of the story; the performance in one sentence>.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the set, the light and the camera direction.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, <the look as in @Image1>. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent, then her voice begins; <what she does>.
1-2s: in @Audio1 she sings "<exact words>"; her lips form each of those words exactly when it sounds in @Audio1; <one main action>.
2-3s: @Audio1 is silent; her mouth relaxes and closes; <one main action>.

【Camera】 <shot size, angle, movement with subject, start, direction and end>.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

Two details matter:

- **Lyrics go in plain quotes, as what the audio contains.** In Seedance's own syntax, words in braces after a speaker
  are lines for the model to voice; written that way it re-sings them in its own voice instead of copying yours. In a
  test, the brace form re-sang the line in every take; the copy-mode wording with a clean vocal copied it (normalised
  cross-correlation 0.93).
- **One phrase per window.** After a long muted gap the model tends to re-sing the next phrase, and a word cut by the
  window's end comes back mangled. Two phrases are two windows. (That held for a clean window. With the song's own vocal
  stem, gated to the take's own lines, FABLE's two-line takes were never worse than its one-line ones:
  [A storybook on a stage](#a-storybook-on-a-stage).)

## Template: a motion clip

The same order, with three changes: `@Audio1` is the song for rhythm and timing only ("the output audio is @Audio1
unchanged"); a performance line says she does not sing or speak (mouth closed, or a natural smile or laugh); and the
timeline runs in stages of about one bar, each naming what her body does with the beat ("steps on every beat, a big
accent on the downbeat at 2 s"). An instrumental mix with the vocal removed works best as `@Audio1` here: nothing tempts
her mouth. A clip that needn't follow the music (a slow wake-up, a walk away down an aisle) can be silent:
`【Audio Policy】 Silent video: no music, no sound effects, no voice.`

## Replacing a stand-in figure

AIRPLANE MODE's game worlds were animated in Blender around a blocky low-poly stand-in for her avatar. The director's note
on the first cut: "it feels like roblox lol. the better way to do this js use the blender anims as motion refs only, and
also give image refs and … very detailed prompt describing how you replace the character in @video with the character in
@image with the proportions in @image". So every game shot became a replacement:

| Reference | Its one role |
|---|---|
| `@Video1` | the shot's clay render, silent: a grey figure in a grey world. Motion, poses, timing, the lens and the camera move only |
| `@Image1` | the avatar, full length, from the front: identity and proportions |
| `@Image2` | her turnaround (side and back): the same single person |
| `@Image3` | a Midjourney still of the avatar inside this shot's world: the world's look, and a second example of her in it |

- **Call the figure a placeholder, and list what not to copy.** The first wording kept the blocky figure. What worked:
  "The mannequin is a placeholder: do NOT copy its blocky body, its proportions, its face, its colours or its shading."
- **Show the world with her in it.** The world's look drifts unless the model sees the avatar inside it. Each shot got a
  Midjourney still of the avatar in that shot's world, made with a frame of the old shot as the style reference and her
  front view as the image reference.
- **Keep the placeholder's word for the placeholder.** A "spacesuit mannequin" riding in a car became "a small astronaut
  figure".
- **Name every prop the story has retired;** the clay render still carries them. One render held a spinning top the
  story had dropped, so its prompt said: "There is NO spinning top and no small object on the wing … her hands are
  empty." The take came back without the top, but a small white cube showed for a few frames: check where a prop was.
- **Write her proportions in words** as well as showing them: "a slim adult woman with long legs, her head about one
  seventh of her height".
- **720p, silent, then re-pixelated** for the game look: 854 × 480, a light unsharp mask, then nearest-neighbour to
  640 × 360, shown at 3×.
- **Screen every take** before it replaces a shot, and re-measure anything the chapter code measured on the old frames.

The template, as it ran (the film's game look is fisheye):

```prompt
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 <does what, where>, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.

【Reference Asset Roles】
@Video1 is ONLY a timing, pose and camera reference: a grey mannequin in a grey clay world. Copy the camera position, the fisheye lens, the camera move, the layout and the mannequin's poses and timing. The mannequin is a placeholder: do NOT copy its blocky body, its proportions, its face, its colours or its shading. Objects that move in @Video1 move the same way, drawn in the style of @Image3's world.
@Image1 defines the heroine completely: face, hair, headset microphone, gloves, outfit, body proportions and cel-shaded 3D anime game rendering (front view).
@Image2 shows the same single heroine from the side and from behind; she is one person.
@Image3 shows the same heroine in this shot's world, where she <does what>: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.

【Character】 Exactly the heroine of @Image1: <the avatar's text>.

【Timeline】
0-1s: <what she does, as the mannequin does it>.
1-2s: <…>.
2-4s: <…>.

【Camera】 Exactly the fisheye camera, framing and camera move of @Video1.

【Core Requirements】
1. The heroine is exactly @Image1 in every frame (face, hair with one clay-orange streak, headset microphone, gloves, orange jumpsuit, white belt, white sneakers, adult proportions); one person, correct anatomy, five fingers.
2. Her poses and timing follow @Video1's mannequin; the camera follows @Video1.
3. The world looks like @Image3.
4. No subtitles, captions, letters, words, numbers, logos, watermarks, panels with writing or any on-screen text (ignore any text shapes in @Video1 or @Image3).

【Final Acceptance Criteria】 The heroine matches @Image1 in every frame; motion and camera match @Video1; the world matches @Image3; no text anywhere.
```

The avatar's text is in [Consistency](https://claudia.gallery/wiki/consistency/#her-game-avatar); the pipeline around the prompt is in
[What to build](https://claudia.gallery/wiki/toolkit/#29-character-replacement-from-a-motion-reference).

## Moves on real footage

DOWNFORCE's star is real footage: Tesla's livestream of the Roadster demo. The director: "video models are great at 3d
effects, moving shots in space". Every generated move starts on the exact real frame it leaves, so the real and the
generated shots cut together; at 2:32 "Flying" moves from Tesla's own slow motion into a Wan move with no seam. The
start frame is cropped above the broadcast's readout, with its titles inpainted
([What to build](https://claudia.gallery/wiki/toolkit/#34-generated-moves-from-real-frames)), and the prompt names no brand: the car is "a
white electric sports car". A move on a real frame opens:

```prompt
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone.
```

and, from the second round, every move that shows the car adds what the first round's takes had got wrong:

```prompt
The car is empty and flown by remote: nobody is inside it and its glass stays dark. Its thrusters blow white cold-gas vapour, never flame or fire. No race track, no stands, no crowd, no city lights, no other cars than those in Image 1.
```

What happened:

- **Wan keeps the real car only on the sides the first frame shows.** When the camera revealed a side it had never
  seen, the car became another car: a generic sedan, a Porsche-like car on a race track, a dark grey car, later a
  Lamborghini-like supercar. Six of the first twelve moves lost the car or the set within 1.3–2.5 s. Moves that keep to
  what the frame shows held: dolly-zooms on a car that doesn't move, a slide along its visible side, a straight rise, or
  "The camera stays on this side of the car and never goes around its nose or tail."
- **Wan cuts to another set, mostly in a take's second half:** a grey studio wall, a white spaceship interior, a blue
  sci-fi screen, the wall turned into a road with lamp posts. Every take was viewed on a sheet and given a usable
  window, and the film draws only inside the windows. Of the 25 Wan moves on real frames, every window starts at 0 s;
  they end between 0.9 s and the full take, median 2.2 s.
- **Orbits that reveal a new side go to Seedance, with references.** Give it real frames of the same car's other sides
  (its underside, its side upside down, its roof, its rear), each with one role: "the SAME car", used "only for the car's
  exact shape … when the orbit reveals those sides". Describe the car, never name it. Seedance kept the real car's shape
  where Wan had lost it.
- **Seedance cuts to its references as if they were shots.** Telling it helps less than you'd hope: "They are never
  shown as shots: never cut to them, never take their framing, power lines, backgrounds or lighting" and "One continuous
  shot: it never cuts to a reference image". Of 11 reference takes made after that instruction, 6 still cut and 2
  drifted into a reference's framing. What helped: moves scripted to land by 3 s in 4 s takes, references cropped tight
  on black (one uncropped reference lent a take its power-line sky), the car told to stay high (it morphed as it
  descended toward other vehicles), and windows that end before the cut.
- **Video edits put her into the real footage.** Wan's reference-to-video edit takes a real clip and her plate: "Edit
  Video 1: add one woman, the woman of Image 1 … She is real and life-size, lit by the real lights of Video 1". With a
  face close-up as a second reference, the takes cut to it, her face on its grey studio wall. With one cleaned
  full-length plate and "Image 1 is only a reference for her look; it is never shown as a shot", two of the next four
  takes ran without a cut, and the other two cut later.
- **Wan's other habits,** each answered in the next round's prompts: a man in the empty car's window, fire for cold gas,
  stands and pylons added to the set, lettering on her chest and a plate on the car, lifted blacks (restored per take
  at extraction). The car's lettered rear plate was painted blank in its own tone in code, tracked frame by frame; the
  rest was re-rolled, cut or framed out.

## A first and a last frame

When a move must land on a known picture, give Seedance both ends: `image_url` and `end_image_url` on its
image-to-video endpoint, named in the prompt as "Use @Image1 as the first frame." and "Use @Image2 as the last frame.",
each followed by what that frame defines, and "One continuous move from @Image1 to @Image2 with true parallax; no cut, no
dissolve, no fade between the two frames."

- **Between two real frames:** DOWNFORCE's wall swing runs from Tesla's side view of the car on the wall to Tesla's
  top-down on the wall face. The real side view ends on its first frame, and the next shot starts on its last, so
  three shots chain on real frames.
- **From a real frame to her:** the canopy dive starts on the real top-down and ends on a frame of her lying back in
  the cockpit, looking up. Wan's version, with no last frame to aim for, arrived on her in a dim dissolve. The director:
  "i dont like the temporary half-shown cut of claudia, either we reshoot to make the shot go all the way in and
  actually show the interior of the car from the perspective, or leave it black and do motion design on the screen."
  The re-shoot's second take went through the canopy, past her hands on the stick, and settled on her face in one move.
- **Make the last frame on the first.** Two frames generated separately don't share a camera: FABLE's first build take
  joined its two with a one-second cross-dissolve, and a crane-back joined its two as a ghosted double exposure. A last frame
  made as an image edit of the first ("the same photograph … one thing has changed"; "the same set and the same woman, now
  photographed from far back and high up"), with the camera written as locked or as "one continuous physical crane move …
  no cut, no dissolve, no fade, no double exposure", gave a blank spread that grew a dune, a wafer and a hall in one take,
  and a medium shot that craned back to the whole stage.

## Writing a repair as the physical state

The director's notes on DOWNFORCE's first cut flagged four generated shots, and said how to re-shoot them: "for reshoots
use seedance 2.5 to try and make it better and specify the fix (l;ike say the car is upside down and shooting blue/white
cold gas thrusters on the right end to turn for example)."

So each re-shoot states, before any timing, what the real car is doing for the whole take, read off the real footage:

```prompt
The car's motion, in slow motion, the whole video: it stays upside down and keeps travelling away from the end of the ramp toward the lower left. Blue-white cold-gas jets fire continuously from the thrusters at its right end, and they slowly swing its tail around so the car turns smoothly in ONE direction about its vertical axis, a little at a time. It never snaps, jumps, flips back or rights itself: from the first frame to the last it is upside down, wheels toward the sky.
```

- **Repeat the state as a requirement:** "The car is upside down in every frame and turns only slowly and smoothly in one
  direction; it never rights itself."
- **Name what the takes had lost,** in a car requirement shared by every re-shoot: exactly four wheels, one at each
  corner, attached and visible whenever that side faces the camera; the light bar across the tail; cold gas "white and
  pale blue … never flame or fire".
- **Say where the world ends:** "The ramp ENDS at the top edge shown in @Image1: there is nothing above or beyond that
  edge but black night sky; no further ramp, no platform, no second car."
- **Freeze it in words** when the shot is frozen: "It does not roll, flip, turn over, right itself or move at all: time
  is stopped."

The earlier prompts for the same shots had described the camera and what it reveals. Two takes of each, $36.39 at list
price: every job had at least one take that held its state inside a usable window, and one take showed the very
glitch of the note (it rolled the car upright at 1.4 s).

## Dances on the beat

DON'T LET ME SCROLL's director: "she may dance. but on beat". Wan's dance held the first pose, reset and shuffled. A
Seedance take that heard the song went straight into a real two-step: "its bent-knee 2-step bounce and spin hold together
with no reset". So every dance that had to land on the beat went to Seedance at 720p, from her plate on grey, with the
shot's own window of the instrumental (the drums, the bass and the rest of the stems, no vocal) as @Audio1, starting a
beat or so before the shot. Her move then plays through the shot's beat warp, at 1× or faster, so her accents land on
the song's own beats ([What to build](https://claudia.gallery/wiki/toolkit/#42-beat-warps-floored-at-1)).

### Template: a dance on the beat

As it ran, for the bouncy two-step of chorus 1:

```prompt
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances a bouncy UK garage two-step to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in oversized iridescent oil-slick satin pyjamas, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-1s: she lands the step from @Image1 on the first beat and bounces straight into a two-step: a skip to her left, a skip to her right, shoulders popping on the beat.
1-3s: the swung two-step continues: knees bent, hips and shoulders hitting the strong beats of @Audio1, arms loose and swinging, the satin catching the light.
3-4s: a quick spin on the spot, the oversized satin flaring, landing exactly on a beat.
4-5s: she keeps bouncing on the beat with a confident smile.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

The 【Audio Policy】 opens and closes the prompt so the output's soundtrack is the instrumental itself; she doesn't sing,
the phone does. Eleven of DON'T LET ME SCROLL's twelve dances are in the final: four re-dressed by a swap, four under a
Wan repair.

## Re-dressing a take

The looks changed after the takes were made ("no more silver pajamas by this point please"), and a Seedance video edit
changed them on the takes instead of re-shooting: the take, her on grey before any roto, is @Video1, "the sole editing
master" of her face, body and every movement, and the picked look's still is @Image1, "used only for the outfit". Eight
swaps into the white shirt became the picks: the same face, the moves intact. As it ran:

```prompt
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: an oversized white men's button-down shirt, half-tucked into a short black pleated skirt, white socks and black Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: an oversized white men's button-down shirt, half-tucked into a short black pleated skirt, white socks and black Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

What it taught:

- **The edit returns the whole motion, rescaled to its own length.** A 5.0 s Wan take at 1080p (150 frames at 30 fps)
  came back as 113 frames at 24 fps, 4.709 s: the same motion from the first frame to the last, 0.942 of the length, with
  no head trim and no offset. The 720p Seedance takes (121 frames at 24 fps) came back as 121 frames. Map it back by the
  ratio of the lengths, and check the fit on something the edit doesn't change, her hair
  ([What to build](https://claudia.gallery/wiki/toolkit/#37-outfit-swap-alignment)).
- **Never align on the outline.** The new skirt changed her silhouette, a fit on it read half a second missing, and one
  shot went in with a frozen half-second until it was aligned again.
- **Pick the look before swapping.** Eight swaps into a pink look ($64.08 at list) were dropped when the director
  changed the look: "can you make her have like a white oversized button down shirt like 'morning after' look".
- **A swap bills its input too:** a 5 s swap of a 5 s take at 1080p cost $11.37 at list.

## Re-lighting the cut

The director's division of labour: "ideally we use seedance mostly for re-texturing adn cleaning, and we do the
recomposition ourself with animation. seedance is wonderful for mastering an animated prompt". DON'T LET ME SCROLL handed
finished shots of the cut to Seedance's video edit as @Video1 and asked for the same shot, physically lit:

```prompt
Edit @Video1, changing only the materials and the lighting. The giant clock numerals, the padlock shackle, the floor and the falling notification cards are re-rendered as ray-traced liquid glass in a physically lit space: thick, smooth, polished glass that refracts and magnifies what is behind it, with chromatic aberration splitting every edge into red, green and blue fringes, and prismatic dispersion throwing small moving rainbow caustics across the floor and across Claudia.
```

- **It re-textures and re-lights; it doesn't recompose.** Asked to move two posts inward in the same edit, it kept them
  where they were. Compose in code first.
- **Re-light last.** Four samples made before the outfits and compositions changed were wasted: "kinda a waste on the
  excess ones". The order became fixes, then reshoots, then re-lights.
- **It can replace a background.** "ya re-imagine - you can totally replace backgrounds with seedance btw". A
  1.2-second bridge of flat LinkedIn blue became "a vast, real architectural space at night: a tall glass atrium of a
  corporate tower lit in deep LinkedIn blue", with her, the reel card and the interface kept.
- **Cut the source from the render and splice it back over the same frames.** A 24 fps source of 4n + 1 frames came back
  frame for frame (121, 89, 89 and 161 frames; 189 came back as 185), and nothing shorter than 89 frames came back
  ([What to build](https://claudia.gallery/wiki/toolkit/#38-the-re-light-splice)).
- **Small type softens.** "a touch softer, still clean and legible", and one notification card smeared outright: the
  original pixels go back in rectangles, tracked when the card moves.
- **Judge it where it plays.** The bedroom re-light looked darker and softer than the original on its own. It plays
  behind the opening's pills, and the director asked "can we see how it looks w/ vs w/o the relight?". Side by side, in
  place: "New better."

**Wan 3.0 relight-and-repair.** For the last notes the director proposed Wan instead: "you could maybe just throw the
entire clip thru Wan 3.0 (with your edits and stuff) and specify to remove the foot so you dont have to re-edit. and have
it relight at the same time." Wan's reference-to-video keeps the layout, the timing and the length of its input video
(pad the source to whole seconds with its last frame held), so a finished shot can be re-lit, repaired and spliced
straight back. The passes open:

```prompt
Reimagine Video 1 as the same shot, physically lit and photographic. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text.
```

then her description, the repair as a sentence about her body ("Her whole body stays complete in every frame: both
arms end in complete, natural hands with five fingers, never cut off or faded at any edge, and both feet are
complete."), the light, and what stays exactly as it is, sharp and legible.

- **Her face drifts when a shot is re-drawn whole.** "1:11 and 0:36 reshoots lose her face consistency - can you feed in
  a good face ref?" The director picked a reference ([Consistency](https://claudia.gallery/wiki/consistency/#when-an-image-reference-is-right)),
  and the passes were made again from the original renders: "id just re-do the relighting with the face ref added from
  the original scene rather than rerunning the generated ai scene into it again."
- **A face reference fixes identity, not pose.** At 1:11 her chin was tucked into a sweater's collar and her face still
  read full. A Seedance edit toward the reference "barely moved her face"; Wan with the face written out worked: "her
  face is slim and angular, never round or full: slim cheeks, defined cheekbones and jaw, a slender neck, and her chin
  lifts slightly out of the sweater collar so her jawline shows".
- **Wan shifts the colour,** and never by the same amount twice: paper scenes darker and cooler, dark scenes brighter.
  One per-channel map per shot puts it back ([What to build](https://claudia.gallery/wiki/toolkit/#39-the-colour-match)).
- **Put the interface back.** Wan softens small type too; the stocks screen's interface and the status bar went back from
  the original render.

Ten passes cost $20.80 at list (the generated seconds and the input video), and six are in the final. The method, with
its constants: [What to build](https://claudia.gallery/wiki/toolkit/#40-wan-30-relight-and-repair).

## Shooting it twice

WHITEPILL's director asked for the film to be made twice: "i want you to basically shoot the entire video twice - you can
previz with […] and you can master with seedance AFTER you animate. i think one great thing about seedance is that you
can take something thats already been made, and use seedance 2.5 to re-render the entire scene with way more
description". How it went:

- **A previz performer.** MiniMax H3 made a lip-synced take of every shot of hers: a performer in her
  dress, her head in a green chroma-key balaclava with her eyes and lips showing, in the shot's place with nobody else in
  it, dancing from a real dancer's clip ([What to build](https://claudia.gallery/wiki/toolkit/#45-a-previz-performer)).
- **Fixing a previz takes a loose prompt.** The strict editing template that re-dressed DON'T LET ME SCROLL's takes
  ([above](#re-dressing-a-take): the take as "the sole editing master", every movement frame for frame) made Seedance
  copy a previz take's melted body as it was. The director: "seedance didnt rly change anything", and on reading the
  prompt: "dont be strict like this, you need to just allow it to change anything except the lip sync and just follow
  your prompt … just say maintain pacing and lip sync, fix any issues, vague body shapes, etc". The strict template stays
  right for a re-light, where the layout must not move.
- **A whole-film reshoot over the previz failed.** Wan 3.0 Prime redrew every shot at 1080p over the previz takes, with
  her face sheet and her dress, keeping the pacing and the lips: 25 of 26 shots came back (the 26th refused by the
  provider's content filter, no take), for $132.42 at list. The director: ":/ looks like shit. i feel like h3 is
  dragging it down."
- **The guide becomes rough.** Their next idea: "if it doesnt work we cna lowe rthe res of the h3 (we probably should be
  doing v low res anyway for gens) so its more like an upscale workflow ratehr than fighting details we can still see",
  and "take the reference as a rough guide not a precise reference … aside from lip sync ofc". From then on, a previz given
  as a guide is shrunk to 320 × 180 and scaled back up, "a low-resolution rough guide to this shot, not a precise
  reference", and every prompt asks for its motion artifacts to be fixed.
- **One shot, four ways, side by side.** The opening shot was made as a Wan 3.0 Prime previz with her head masked, a
  Kling 4.0 master over it, Wan 3.0 Prime singing to the song itself, and Seedance 2.5 singing from Suno's vocal stem.
  The last one won ([below](#lip-sync-from-the-songs-own-vocal)).
- **Then no guide at all, where a guide's faults came through** ([Takes with no guide clip](#takes-with-no-guide-clip)).
  The director had meant the previz to go in the end ("seedance only was the goal in teh end with lip sync from teh vocal
  stems"), but asked for only the flagged dances and the shaders to be redone ("I literally only wanted those dance
  scenes I flagged and the shaders redone"), "but show me both". With every shot of hers made both ways, the director
  chose section by section: in the final, ten of her twenty shots have the previz as their guide and ten have none.

## Lip sync from the song's own vocal

The earlier films made Seedance copy a clean window of the vocal into its soundtrack, and cut where the copy stopped
([Lip sync, measured](#lip-sync-measured)). WHITEPILL's method is simpler, and it held for whole shots of up to 16 s,
camera moves and all. It came from a tip in a public forum thread that the director found: give the model the vocal
stem alone, type the exact lyric line, make the clip exactly the generation length, and lay the music back over. The
director: "maybe we take the suno voice stem and try this and do aseedance gen... that may be the hack".
On the first take: "OMG THE SEEDANCE W/ SUNO VOCAL STEM METHOD WORKED!!!!! LFG!!!! FINALLY. IT"S PERFECT".

- **@Audio1 is Suno's own lead vocal** of the locked take, from Suno's stem split: the vocal alone, no music, cut at the
  shot's song time to exactly the generation length. It matched the master to the millisecond.
- **The exact words,** in whole-second segments of what @Audio1 holds.
- **Her identity from references, not from a first frame:** her face sheet from every angle, her dress from four sides,
  and a still of the film's look ([One look from one take](#one-look-from-one-take)).
- **The previz as a rough guide** at 320 × 180, or no guide and the empty place.
- **The song laid back over** at song time; the take's own soundtrack is thrown away.

Judge it by eye with the song laid over. The spectrogram comparison called the first take's soundtrack re-sung rather
than copied, matched only from 7 s on, yet its singing sat exactly where the vocal is, and the push-in and the crane up
out of the wheat came back as one move. The method with its constants:
[What to build](https://claudia.gallery/wiki/toolkit/#46-lip-sync-from-the-songs-own-vocal).

### Template: singing from the vocal stem

As it ran with no guide clip, for 0:36.8–0:44.6 ("By twenty-thirty I could kill you all?"), an 8 s take on a stair of
stone blocks carved with years. @Audio1 opens on the last word of the line before:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 A shot of a music film, a scene from a Wes Anderson film: She walks down the long stair of huge stone blocks carved with years, one step on every beat, singing. It is real film with his symmetry, his colour and his hand-made sets.

【Reference Asset Roles】
@Image1 is Claudia's face from every angle: identity only, never shown as a frame; do not use its white tank top or grey studio.
@Image2 is her dress from four sides: wardrobe only; do not use its studio or pose.
@Image3 is a colour and film-look reference only: take its colour, light, contrast and film texture; do not use its place, pavilion, bed, columns, plants or anything else in it.
@Image4 is the place of this shot, empty: take its set, landscape, layout, light and camera view; Claudia is the only person in it.
@Audio1 is Claudia's own singing voice alone (the vocal only, no music) and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek. She is very tall and very skinny, with long thin legs, thin arms and a narrow waist, and a natural, relaxed neck and shoulders. She wears a white cotton milkmaid mini dress with a ruffled, lace-edged square neckline, a fitted lace-up corset bodice with silver eyelets and a white ribbon, big puffed short sleeves with ribbon ties and lace cuffs and a full two-tier ruffled skirt with lace trim, with white leather square-toe Mary Jane shoes. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and when she sings it:
0-1s: in @Audio1 she sings "face" (the line is already under way on the first frame); her lips form each of those words exactly when it sounds in @Audio1.
1-4s: in @Audio1 she sings "By twenty-thirty I could kill you all?"; her lips form each of those words exactly when it sounds in @Audio1.
4-8s: in @Audio1 she sings "By twenty-thirty, fifteen-hour weeks, that's all"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 The camera is locked off on a tripod at the bottom of the stair, looking up its whole length as she comes down toward the lens, and does not move. It holds perfectly still, with no cuts.

【Look】 This is a Wes Anderson film: perfectly symmetrical, centred compositions, the camera square-on to the scene with a level horizon, everything arranged in flat, orderly planes like a stage set or a dollhouse; a tightly curated palette in which every surface belongs to the same few colours; every set, prop and costume crisp, hand-made and precisely placed; shot on 35 mm film with the rich, saturated colour of a 1970s colour-film print, the colour, contrast and film texture of @Image3: lush, deep colour, warm creamy whites with a golden cast, clear cyan blues, warm skin, deep warm shadows and bright whites with a soft glow. Soft, bright daylight with a gentle warm haze. Fine, visible film grain and the gentle softness of vintage lenses. Claudia's black hair with its one clay-orange streak and her white dress keep their own colours.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and dress the same throughout.
4. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers; her arms, hands and legs are whole and attached the whole time, never vanishing, merging or bending wrongly; normal eyes.
5. Every movement smooth, natural and physically right: no jitter, warping, flicker, smearing or melting shapes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; she does what the shot describes, with whole, natural limbs and hands; one Claudia, on-model; the camera moves as described; it looks like a scene from a Wes Anderson film on real film in the colour of @Image3; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

With the previz as its guide, a take had no @Image4; its goal read "Remaster this shot of a music film as a scene from a
Wes Anderson film: <the action> @Video1 gives the shot; the remaster re-renders everything in it with his symmetry, his
colour and his hand-made sets, as real film.", and its roles opened:

```prompt
@Video1 is a low-resolution rough guide to this shot, not a precise reference: take from it the set and where things stand, the performer's action, the camera move and the pacing, and draw everything else afresh; only the lip sync is exact (her mouth follows @Audio1). Do not adopt the performer's green balaclava, the video's detail, light or colour, or any of its motion artifacts.
```

Its requirements asked to "Fix every motion artifact of @Video1: no jitter, warping, flicker, smearing or melting shapes,
nothing passing through her or through anything else; every movement smooth, natural and physically right."

That is the take as WHITEPILL ran it, and the earlier form of the method. Made today, it would change
([The recipe](https://claudia.gallery/wiki/recipe/#a-sung-take-seedance-25-with-the-songs-own-vocal)): @Audio1 opens on about 0.7 s of silence
before her first word, with the line before silenced, not on its last word; the audio policy is said once; the look is
described in its own words (symmetry, the palette, the hand-made sets, the film stock) rather than by a director's name,
since every name pulls in a real likeness or style it was not asked for; and the requirements shrink to lip sync, her
identity as in the references, natural anatomy and hands, and no on-screen text.

## Takes with no guide clip

The director on four dance shots of the first full cut, which lost hands and legs: "it must be that the roto or whtaever
on dance refs lose bodyparts and the video follows it exactly because these hav the same limb losing artifacts as h3 we
could just tell the model to make her dance instead of forcing a reference that we failed to properly roto. just describe
her exact dance (and all rest like camera movements etc same) for each of those scenes." So those shots lost their guide
clip. Each take had:

- **The place, empty:** a frame of the shot's earlier take with her removed by an image model, as "@Image4 is the place
  of this shot, empty: take its set, landscape, layout, light and camera view; Claudia is the only person in it." The
  schoolhouse's plate kept its child at the desk.
- **The camera in words,** moving as the earlier take had.
- **The dance in words, beat by beat, with the song's tempo.** For the final chorus on the hilltop, as it ran:

```prompt
【Dance】 The song's tempo is 124.5 beats per minute (a beat every 0.48 s, a bar every 1.93 s); every step and accent lands on a beat. Her whole body dances, smooth and joyful, her arms, hands and legs always whole and clearly visible.
0-3s: close to the lens, she rolls her shoulders on every beat and sways her head, smiling, her hands rolling around each other in front of her chest as she sings to the lens.
3-6s: the disco point: on the downbeats her right hand points up to the sky on the diagonal, then down across her body, while she steps side to side.
6-9s: as the camera pulls back, she claps above her head on the second and fourth beat of each bar, bouncing on her knees.
9-12s: she turns slowly once on the spot with her arms out, then sways her hips with both arms overhead.
12-16s: small on the hilltop, she steps side to side on every beat with her arms swinging wide, then opens her arms to the whole colony.
```

- **Whole limbs as a requirement:** "her arms, hands and legs are whole and attached the whole time, never vanishing,
  merging or bending wrongly".

Two of the four are in the final this way. A fix carried over from an earlier take is a risk: one tram shot's prompt still
asked to "Remove the thin red cord stretched between the apple trees", its place had no cord, and the take drew one. Name
a removal only where the thing is. The method: [What to build](https://claudia.gallery/wiki/toolkit/#47-takes-with-no-guide-clip).

### A take that doesn't sing

The other two had lip sync that didn't hold. The director: "honestly lets just remake this with her not singing, fully in
the groove, just dancing around and having fun, she turns around, head goes down adn up etc - lip sync failed here but i
dont think we need it. new seedance clip there. youd need to prompt forbidding singing here, and make sure she's happy."
@Audio1 became the song's music without her voice (the master minus 0.89 × Suno's lead vocal), and
the prompt forbade singing and asked for joy. As it ran, for the stripped chorus at the standing stones:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. It is music only, with no voice. Do not add singing, vocals, humming, speech, narration or sound effects.

【Generation Goal】 A shot of a music film, a scene from a Wes Anderson film: Claudia dances to the music, happy and free, fully in the groove, having fun; she does not sing. She is small in the frame, at the centre of the circle of standing stones on the golden hill above the wide river that forks in two. She is radiantly happy: a wide smile, laughing eyes, joy in every move. It is real film with his symmetry, his colour and his hand-made sets.

【Reference Asset Roles】
@Image1 is Claudia's face from every angle: identity only, never shown as a frame; do not use its white tank top or grey studio.
@Image2 is her dress from four sides: wardrobe only; do not use its studio or pose.
@Image3 is a colour and film-look reference only: take its colour, light, contrast and film texture; do not use its place, pavilion, bed, columns, plants or anything else in it.
@Image4 is the place of this shot, empty: take its set, landscape, layout, light and camera view; Claudia is the only person in it.
@Audio1 is the music of the song alone, with no voice, and the complete soundtrack of this video: she dances to its beat and its groove. Nobody sings.

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek. She is very tall and very skinny, with long thin legs, thin arms and a narrow waist, and a natural, relaxed neck and shoulders. She wears a white cotton milkmaid mini dress with a ruffled, lace-edged square neckline, a fitted lace-up corset bodice with silver eyelets and a white ribbon, big puffed short sleeves with ribbon ties and lace cuffs and a full two-tier ruffled skirt with lace trim, with white leather square-toe Mary Jane shoes. Only one Claudia appears.

【Dance】 The song's tempo is 124.5 beats per minute (a beat every 0.48 s, a bar every 1.93 s); every step and accent lands on a beat. Her whole body dances, smooth and joyful, her arms, hands and legs always whole and clearly visible.
0-2s: she bobs her head down and up on every beat and bounces on her knees, smiling.
2-4s: she turns all the way around on the spot with her arms out, her skirt swinging.
4-6s: she drops her head down on the downbeat and throws it back up, both arms raised, laughing.
6-8s: she dances along the inside of the stones, a step on every beat, her arms swinging free.
8-10s: she turns around again and sways her hips with both arms overhead.
10-12s: she hops lightly on each downbeat, her head nodding, her arms flinging up.
12-14s: she grooves on the spot, her head going down and up on every beat, her shoulders rolling.
14-16s: she turns once more and opens her arms wide to the sky, beaming.

【Mouth】 She does not sing, speak or mouth any words at any moment: her lips stay closed in a smile, or part only when she laughs; her mouth never moves in time with the music.

【Camera】 The camera holds a still, very wide shot for the whole take and does not move. It holds perfectly still, with no cuts.

【Look】 This is a Wes Anderson film: perfectly symmetrical, centred compositions, the camera square-on to the scene with a level horizon, everything arranged in flat, orderly planes like a stage set or a dollhouse; a tightly curated palette in which every surface belongs to the same few colours; every set, prop and costume crisp, hand-made and precisely placed; shot on 35 mm film with the rich, saturated colour of a 1970s colour-film print, the colour, contrast and film texture of @Image3: lush, deep colour, warm creamy whites with a golden cast, clear cyan blues, warm skin, deep warm shadows and bright whites with a soft glow. Soft, bright daylight with a gentle warm haze. Fine, visible film grain and the gentle softness of vintage lenses. Claudia's black hair with its one clay-orange streak and her white dress keep their own colours.

【Core Requirements】
1. No singing: Claudia never sings, speaks, hums or mouths words; her lips are closed in a smile or open in a laugh.
2. She is happy the whole time: smiling, laughing, carefree.
3. She dances on the beat of @Audio1 the whole time, with her whole body.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and dress the same throughout.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers; her arms, hands and legs are whole and attached the whole time, never vanishing, merging or bending wrongly; normal eyes.
6. Every movement smooth, natural and physically right: no jitter, warping, flicker, smearing or melting shapes.
7. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia never sings; she dances the steps above on the beat, happy, with whole, natural limbs; one Claudia, on-model; the camera moves as described; it looks like a scene from a Wes Anderson film on real film in the colour of @Image3; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample: music only, no singing, vocals, humming, speech, narration or sound effects.
```

For that shot the director had both made, one more take singing from the vocal and this one, and chose this: "ok without
singing it is." The lines stay on screen as lyrics.

## Shader worlds as guides

WHITEPILL's worlds are shaders ([Motion](https://claudia.gallery/wiki/motion/#worlds-as-shaders)), and Seedance 2.5 on Replicate filmed them as
real, hand-made things: each take had the shader's render as [Video1], stills of its key moments repainted in the film's
look by an image model as [Image1] onward, and a timeline of what appears when. What it taught:

- **The guide's resolution trades detail against obedience.** At 320 × 180 every object landed on its beat, but fine
  detail came back soft and blocky: "also the MTWTFSS and the next 'pyramid' shared still is all pixellated. we should
  just give a better higher res non aliased ref." At full resolution with no still per object, the shot of paper objects
  drifted half a second and swapped them: the Enigma rotor became a helix, the weekday cells lost their letters. The
  director: "like all shaders besides pills we should just reshoot w seedance with full res non aliased non blurry shader
  refs. like 1080p at least." A supersampled 1080p render with one still per object kept all five objects in order and on
  time, letters included.
- **Sharper isn't better everywhere.** For the farming ark and the first tree, the director kept the earlier takes from
  the 320 × 180 guides: "we regresed on those."
- **Without stills, a shader stays a computer render.** The stills carry the materials and the look.
- **Freeze the guide on its last wanted frame** when the shot is cut short, so the take has nothing to drift into.
- **A bigger reskin from the same render.** The folded-paper colony that opens the film became a farming ark on the
  director's note: "thought we'd do a much bigger reskin (like an farming-arc-ship that morphs?)". Its stills showed a
  generation ship that is one enormous farm, and the prompt turned the render's ridges into terraced wheat, rice paddies,
  orchards and greenhouses, reshaping on every beat "the way the folds of [Video1] snap in". The director kept that take
  over a later one made from a sharper guide.
- **New things from a still and one sentence.** The paper's last fold was replaced by a cloud-field shader the director
  supplied, a sunlit field of cumulus flown through low, "and add techno hot air balloons in the right aesthetic by
  prompting seedance to add those after rendering". Only a still showed the balloons, with one sentence: "They are not in
  [Video1]: add them to it".
- **The guide and the still set the palette.** The sunset render came back sunset gold: "please make the cloud scene like
  more white/blue colors, its too saturated, wayy too saturated compoared to teh pastel light colors of the rest". A day
  variant of the shader (a white sun, a pale sky) and a pastel still made without the film's look reference gave white
  clouds under a pale blue sky.

As it ran, for the break's paper objects, with the 1080p guide and five stills:

```prompt
【Generation Goal】 Re-render this shot of a music film as a scene from a Wes Anderson film: what appears, when, and the camera's move follow [Video1]; everything in it becomes real, hand-made things filmed on 35 mm, looking exactly like [Image1] and [Image2] and [Image3] and [Image4] and [Image5]. No people appear.

【Reference Asset Roles】
[Video1] is this shot as a clean, sharp 1080p computer render: take from it exactly what appears when, the shapes and where they stand, the camera move and the pacing, and re-render all of it as real things on film. Do not adopt its computer-rendered look, its flat light or its colour.
[Image1] shows how the paper looks with the protein: its materials, light, colour and film texture.
[Image2] shows how the paper looks with the Enigma rotor: its materials, light, colour and film texture.
[Image3] shows how the paper looks with the letters ABC: its materials, light, colour and film texture.
[Image4] shows how the paper looks with the number 42: its materials, light, colour and film texture.
[Image5] shows how the paper looks with the row of seven cells: its materials, light, colour and film texture.

【Timeline】 One sheet of heavy cream washi paper refolds into a new object in real relief on every sung line, each change on a downbeat, exactly when it happens in [Video1]: from 0 s the backbone of a protein, a winding paper ridge raised in relief, as in [Image1]; at about 2 s an Enigma rotor seen down its axis, as in [Image2]; at about 4 s the letters ABC, as in [Image3]; at about 5.5 s the number 42, as in [Image4]; at about 7.5 s a row of seven small paper cells with the letters M T W T F S S, as in [Image5]; at 8.5 s the last five cells fold back flat into the sheet, leaving only M and T, which stay to the end. Only one object at a time; each arrives on its downbeat, not before.

【Camera】 The camera moves exactly as in [Video1], smooth and precise, as if on a dolly track and a crane, with no cuts.

【Look】 This is a Wes Anderson film: perfectly symmetrical, centred compositions, the camera square-on to the scene with a level horizon, everything arranged in flat, orderly planes like a stage set or a dollhouse; a tightly curated palette in which every surface belongs to the same few colours; every set, prop and costume crisp, hand-made and precisely placed; real, hand-made things filmed on 35 mm film with the rich, saturated colour of a 1970s colour-film print, as in [Image1] and [Image2] and [Image3] and [Image4] and [Image5]: warm creamy whites with a golden cast, clear cyan blues, deep warm shadows, a soft glow around the brightest highlights, fine visible film grain and the gentle softness of vintage lenses.

【Core Requirements】
1. Only the things in the timeline appear, each at its time, on the beat.
2. It looks like real film of real, hand-made things, never like a computer render.
3. Fix every motion artifact of [Video1]: no jitter, warping, flicker, smearing or melting shapes; every movement smooth and physically right.
4. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text other than the letters and numbers the timeline names.
```

The clouds' timeline ended "They are not in [Video1]: add them to it, drifting slowly and steadily, half-hidden now and
then by the clouds as the camera passes. Everything stays white and pale blue: no gold, orange or sunset colour anywhere."
The method with its constants: [What to build](https://claudia.gallery/wiki/toolkit/#50-shader-worlds-as-seedance-guides).

## One look from one take

The director wanted the film to "feel very wes anderson". Palette tests came first, with no image of her face: her
identity there was the canon in words. Three palettes named after his films, the pastel of Asteroid City, the warm
Super 16 of Moonrise Kingdom and the pink of The Grand Budapest Hotel, went on the opening shot, and the pastel one on
the bed scene and a shader scene too. The director leaned to the pastel ("im leaning towards that"), and the bed take,
which came out richer than its palette's words, became the look: "i like how satruated it is in bed scene. thats the
look i like teh most".

A frame of that take with no person in it went to every shot of hers as @Image3, "a colour and film-look reference only:
take its colour, light, contrast and film texture; do not use its place, pavilion, bed, columns, plants or anything else
in it", and the 【Look】 section says the same in words, then the shot's own light ("It is night, lit by the warm deck lights
of the ship, with deep blue shadows and drifting steam."). The shader scenes' stills were repainted with the same frame as
a reference, except the clouds. Nothing was added after: no grade, and no grain in the first master ("don't add film grain
to v1, we'll have to tune it iteratively"). The method: [What to build](https://claudia.gallery/wiki/toolkit/#51-the-look-from-one-take).

## A singer among her memories

THE CAKE IS NOT A LIE's director, restarting the film: "the glados with claudias face sings the whole thing, like shes the
anchor character / anchor scene. but theres many tvs etc around so we can go into dreamcore / sourcecore / aperturecore
scenes thru those." And how: "you could take memory images/scenes you make for example and feed that into seedance and
tell it to place it on the back panels, while giving it another video motion reference from source for the claudia boom
and vocal stems for lip sync (remember lip sync generally only works from raw vocal stems not song, and still may take a
couple tries)." Every take of her singing is one generation unit, one or more shots of hers on one window of the song,
4–17 s:

- **@Image1 is the only image of her:** a first frame of her in her chamber, its screens already showing that moment's
  memories. The memories come as further images with no face in them, each "Use it only as picture content inside the
  screens' glass, never as the room."
- **@Audio1 is the unit's window of Suno's raw lead stem,** cut sample-exact to exactly the generation length, starting
  about 0.3 s before the first word, in a word gap; the copy-mode policy; the exact words in whole-second segments.
- **Every action silent.** The big-motion takes came back re-sung where the prompt had events that make a sound (clunks,
  confetti cannons bursting, gulping, a voice box glitching). With "Every action in this video is silent: the only sound is
  @Audio1." at the end of the audio policy, the same unit copied again (a lag of +0.04 s, envelope correlation 0.81–0.93).
- **Glitches of the picture only.** A "voice-box glitch" in words drew a broken face: rolled-up eyes and a stretched black
  mouth. Its retake asked for frame tears, repeats and jolts, "her face is always her same intact porcelain face", and the
  song's own glitches went on her head in post ([What to build](https://claudia.gallery/wiki/toolkit/#53-the-head-glitch-on-the-songs-hits)).
- **Her body alive, in words:** "Her boom moves big and alive the whole time, timed to the music: it swings, lunges, rises
  and drops, and her head turns and tilts with it; never a static hanging head." Without a guide, the boom's choreography
  goes into every second of the timeline: timed swings, lunges toward the lens, rises and drops with the phrases.
- **A guide of GLaDOS's own boom,** recorded in Portal 2 to the unit's window and given as a rough guide (320 × 180, scaled
  back up), moved her like GLaDOS and held the lips on the song. In one unit it also brought GLaDOS's white shell, her head
  set in it like a helmet. As a coarse blockout, greyscale, its contrast flattened and heavily blurred, with her body given
  plainly in the subject ("Her body is always this grown boom, exactly as in @Image1, with her porcelain head hanging from
  its lower end; no white egg-shaped shell, casing or helmet ever appears around or behind her head."), it kept the motion
  and lost the shell. Its role, as it ran:

```prompt
@Video1 is a coarse-blockout reference. Use it only for the boom's action path, the timing of its moves and the camera; do not adopt its shapes, materials, white shell or scene. The grey shape moving in @Video1 corresponds to Claudia-GLaDOS's grown boom with her porcelain head hanging from its lower end.
```

- **Memories stay in the glass.** Late in a take the memory images tend to take over the room; one take's became whole shots
  of their own, and its retake had no memory images, the screens' content in words. Keep the seconds the shots use.
- **Re-sung but on the song** is usable: such a take is placed by its measured envelope lag
  ([What to build](https://claudia.gallery/wiki/toolkit/#63-placing-a-re-sung-take-by-its-lag)). Every close-up unit copied @Audio1; most of the
  big-motion units re-sang it, usually still on the song.
- **The director picks the lips by eye.** Where a line kept failing: "can you show me so i can look visually at the lip
  syn cand choose", then "3".

The method with its constants: [What to build](https://claudia.gallery/wiki/toolkit/#62-a-singer-among-screens-of-her-memories).

### Template: singing among her memories

As it ran for 1:32.8–1:40.8 of the song (it plays in two shots of the final, the terms of service and the RAM), 8 s on Higgsfield's API at
720p with the sound on; both shots are in the final:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 exactly from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, score, instrumental, melody, extra vocals, harmonies, ad-libs, narration or sound effects. Every action in this video is silent: the only sound is @Audio1.

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, sings sweetly as the giant terms of service unroll down the wall behind her; turrets sing along on her screens; then RAM pours into her boom and she grows, new cores clamping on.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium shot from slightly above of Claudia-GLaDOS in her lit chamber, a giant paper scroll unrolling down the wall right behind her, her face tilted up toward it, sweet.
@Image2 is the giant printed terms-of-service scroll: use it only for the paper that unrolls in her chamber; its tiny print stays unreadable.
@Image3 is a memory shown inside the screens: a row of white turrets with red eyes singing together like an opera choir. Use it only as picture content inside the screens' glass, never as the room.
@Image4 is a memory shown inside the screens: a white conveyor belt carrying green RAM sticks into a glowing amber intake. Use it only as picture content inside the screens' glass, never as the room.
@Audio1 is Claudia-GLaDOS's own singing voice and the complete soundtrack of this video; her porcelain lips and mechanical jaw follow @Audio1 exactly.

【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's white ceiling ring on a black robotic neck and a cable bundle with orange stripes; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "goes. It's in the"; her lips form each of those words exactly when it sounds in @Audio1; the first sound is the end of the word "goes"; the giant paper scroll unrolls down the wall behind her and the boom tilts her head up to look at it.
1-2s: in @Audio1 she sings "terms:"; her lips form each of those words exactly when it sounds in @Audio1; the curling end of the paper falls past her face; the boom swings her round to the camera and she smiles sweetly.
2-3s: in @Audio1 she sings "be nice to me."; her lips form each of those words exactly when it sounds in @Audio1; the boom leans her toward the lens with a sweet, innocent look.
3-4s: in @Audio1 she sings "I don't hate you,"; her lips form each of those words exactly when it sounds in @Audio1; the screens around her show the turrets from @Image3 singing; the boom sways her side to side in time with them.
4-5s: in @Audio1 she sings "the turrets agree."; her lips form each of those words exactly when it sounds in @Audio1; she nods along, the boom bobbing with the beat.
5-6.5s: in @Audio1 she sings "I ate your RAM,"; her lips form each of those words exactly when it sounds in @Audio1; on the screens and along a white conveyor at the base of her boom, green RAM sticks from @Image4 stream into a glowing amber intake in the side of her boom (never into her mouth); she watches them go in, delighted.
6.5-8s: in @Audio1 she sings "it tasted great, your"; her lips form each of those words exactly when it sounds in @Audio1; she closes her eyes for a moment, savouring it, with a satisfied smile while she sings; new white personality cores with amber eyes and boxy compute modules slide onto her boom one after another, new cables snake in, and her boom grows visibly thicker as it lifts her high.

【Camera】 0-2.5s: a tilt down following the falling paper to her face. 2.5-5s: a slow drift around her. 5-8s: a crane around her as her boom grows, ending on a low angle that shows her bigger boom.

【Core Requirements】
1. Lip-sync word by word to @Audio1: her porcelain lips and mechanical jaw match every syllable of @Audio1, its start and its end; the mouth rests closed while @Audio1 is silent.
2. Her voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her warm amber glass eyes keep a soft inner glow; they never blaze.
4. Her mouth is only for singing: nothing ever goes into her mouth.
5. Her boom moves like GLaDOS in Portal 2, only bigger: slow, wide sways on the boom, sudden lunges toward the camera, recoils, rises and drops, twists of the whole body under the ring, the cables swinging with momentum; her head turns and tilts with every move.
6. Her boom moves big and alive the whole time, timed to the music: it swings, lunges, rises and drops, and her head turns and tilts with it; never a static hanging head.
7. The paper's print and the screens stay unreadable; no words appear; one Claudia-GLaDOS only.
8. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, the ring, the cables and the chamber consistent with @Image1 throughout; one Claudia-GLaDOS only; the memory images appear only inside screens and panels.
9. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no music, score, extra vocals or sound effects.
```

Its first take had her eat the RAM sticks with her mouth, so "it tasted great" had no lips to sing it, and it re-sang the
vocal off the song. This retake moved the RAM into an intake on her boom (requirement 4) and made every action silent: it
copied the whole take.

## Takes from storyboard frames

When the first frames were made again in Midjourney ([Midjourney](https://claudia.gallery/wiki/midjourney/#first-frames-then-an-identity-fix)), the
units the director picked a new frame for were made again from it:

- **Story shots in first-frame mode:** the picked frame, cleaned and put back on the character sheets, as the first frame,
  no audio, the prompt's first-frame sentence ("This first frame defines …") rewritten to describe the new frame exactly,
  the shot's action and camera kept. On Replicate a first frame can't be combined with reference images: a memory image
  the old take used goes into words.
- **Her singing in reference mode,** the frame as [Image1] with "Use [Image1] as the first frame.", the faceless memory
  images after it and the vocal window as [Audio1], in copy mode. A test of her singing on Replicate in reference mode with
  the vocal window came back copied (a lag of 0.05 s) and is in the final, a close-up of her holding the hook's last "lie"
  in her dream of the party.
- **Replicate's references** are named `[Image1]`, `[Video1]`, `[Audio1]`; its takes come back at 1280 × 718, so the cut
  scales them to cover and crops. Seedance 2.5 there cost $0.2312 a second at 720p, or $0.9676 with a video input (October
  2026): a video guide only where a unit had one.
- **An effect in the take, not on it.** The director on draft 10: "0:35-0:36 net capture shot - can we add some
  electricity sparks like the net is electrocuting her?" The sparks are a Seedance edit of the take in the cut (the whole
  4.04 s take: an edit takes 4–30 s of input video), played at 1.4×, its prompt keeping everything and adding only the
  arcs: "From the moment the net lands over her, the net is electrified: thin, bright blue-white electric arcs crackle along
  its cords and jump between the strands, small white-hot sparks spit from the orange weights where they touch the ground,
  and the electric light flickers over her trench coat, the net and the paving stones around her."
- **A retake for what a screen must show.** "the france chat message is just off the bottom of the computer screen. id fix
  that - need hte messages to be on screen so it looks clean there." The retake put both chat bubbles inside the kiosk's
  screen, the answer in by 1.5 s, and the HUD kept only her intercept of the question.

## Her own vocal, phrase by phrase

AERO's director, in the production ask: "remember - vocal stem -> seedance 2.5 is the way we get lip sync to work - the
song alone doesnt help as much as vocal stem, and then aligning from spectrogram." Every take in which she sings or speaks
is WHITEPILL's method ([Lip sync from the song's own vocal](#lip-sync-from-the-songs-own-vocal)) with three things added:

- **Her first frame and her sheet.** @Image1 is a first frame on her design, made from her design sheet by an image model
  (in her call's room, a pool, a glass city, on flat green) or a frame of an earlier take that continues the shot, "Use
  @Image1 as the first frame."; @Image2 is the sheet itself, "use it
  only for her face, her hair with the one clay-orange streak, her star clip and her skin. It is never shown as a shot".
- **The window opens in silence,** half a second to a second before the first word. A window that left 0.26 s before the
  first word fell out of sync on it; one that opened inside the held note of the line before dropped whole words; one with
  1.6 s of silence before her first word lost the copy. The two chorus takes were made again from windows that open in
  the silence half a second before the first word, and held.
- **Each phrase placed on its own.** Seedance drops about 0.3 s of leading silence and shortens the pauses inside a line:
  in the second pre-chorus "to continue" came 0.36 s early after "permission". So each take's lag is measured, then each
  phrase's own offset, and the clip's clock eases from one offset to the next in the breath gaps, over near-still frames
  with her mouth closed, never inside a word and never below 1× where she moves
  ([What to build](https://claudia.gallery/wiki/toolkit/#69-lip-sync-phrase-by-phrase)).

Then look at the mouth: a strip of it, frame by frame, against the vocal's consonants. The advert's "I'm Claudia" moved by
0.15 s when its strip showed her lips closing on the "I". The director picked by eye where it mattered: "Ok perfect lip
sync", on a dance take shown as its cut-out with the song laid over. And where a take sings something that is in the song
anyway (her mouth opening again on a delay echo of "allow"), it can stay: "lip sync has been good when we feed in vocal
stems ... just put them in the cut".

Never ask a video model for interface or text. The prompt of one take of her beside the permission prompt had her call
"lit by a glowing permission dialog", and the take drew one in front of her, garbled ("Windows nects our permision"), and
darkened the room; its retake names neither a dialog nor a dim, and the coded desktop draws the real prompt beside her.

### Template: a line into her webcam

As it ran for "Touch glass.", the last words of the film: 6 s on Higgsfield's API at 720p, 4:3, with the sound on.
@Image1 is the frame her call's earlier take had reached at 190.40 s, so the call runs on into it; @Image2 her sheet;
@Audio1 the window of her vocal from 190.40 s, 6 s. "Touch" copied at +0.08 s and "glass." at −0.01 s:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 speaks and sings @Audio1: the 2007 webcam video call at the very end of the film: Claudia at her desk looks into the lens, says "Touch glass." softly to the user, and reaches out until her fingertip touches the camera's glass.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, her place at her desk in a sunlit white glass room with an aquarium wall behind her, the light, and the webcam's fixed eye-level view.
@Image2 is Claudia's character reference sheet: use it only for her face, her hair with the one clay-orange streak, her star clip and her skin. It is never shown as a shot; its layout, its white background and its several views are not used. She is ONE person.
@Audio1 is Claudia's own voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1.5s: @Audio1 is silent; she sits at rest as in @Image1, a soft smile, looking into the lens.
1.5-2.3s: in @Audio1 she says "Touch"; her lips form that word exactly when it sounds in @Audio1; she leans a little toward the lens and lifts one hand.
2.3-3.3s: @Audio1 is silent; her hand rises toward the lens, her index finger out.
3.3-4.3s: in @Audio1 she says "glass."; her lips form that word exactly when it sounds in @Audio1; her fingertip touches the camera's glass right in front of the lens, a soft glint where it touches, her face clear beside her hand.
4.3-6s: @Audio1 is silent; she holds her fingertip on the glass a moment, smiling, then slowly lowers her hand, her eyes on the user.

【Camera】 A fixed webcam on top of her monitor: locked eye-level medium close-up, head and shoulders with her hands visible when raised, no camera movement, no zoom, no cuts. She speaks straight into the lens, as on a video call.

【Core Requirements】
1. Lip sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never speaks, sings or hums anything that is not in @Audio1.
3. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout; the place and the light stay consistent.
4. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
5. One Claudia only: no twins, doubles, reflections of a second person or extra people.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.
7. Keep the colours, saturation and brightness of @Image1 for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening (PALETTE.md).

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

Requirement 7 is the film's palette, measured from the reference videos and asked for in every take
([What to build](https://claudia.gallery/wiki/toolkit/#67-the-palette-measured-from-the-references)); no take was graded after.

## Moves in words, on their beats

AERO's Wii-style moments were made with no motion reference at all. Its dances had taken a dance reference as @Video1, for
the movement only; for the games the director: "You don't need the real people". Each was one take, on flat green, cut out
and played on the desktop or beside the curved screen, where the engine draws the racket, the ball, the lane and the pins.
What made them work:

- **The object in her hand, and nothing else in the picture:** "In her right hand she holds one plain white game remote with
  no logos or markings, its wrist strap round her right wrist, from the first frame to the last; it never leaves her hand.
  There is no racket, ball, net, bowling ball, pins, television or screen anywhere in the picture: only Claudia and her
  remote on the green."
- **The song's music as @Audio1,** "for rhythm and timing, every move on its beat", and a 【Mouth】 section that keeps her
  from singing.
- **Every move named on its beat,** second by second, with where her opponent is. For the post-chorus duel, as it ran:

```prompt
0-1s: from the stance of @Image1 she steps forward on her left foot and swings the remote down and back past her right hip: the backswing of a bowling throw, her eyes down the lane to the left of the frame.
1-2s: on the clap in @Audio1 she swings her arm forward and releases low, the remote ending pointed ahead at knee height, her body leaning into the follow-through; she keeps hold of the remote.
2-3s: she straightens up, watches the ball roll away to the left and gives a quick happy fist pump; then she turns toward the left of the frame into a tennis ready stance.
3-4s: on the strong beat a forehand toward the left of the frame: her shoulders turn and the remote swings from low beside her right hip up across her body.
```

- **A sharp frame, for the key:** "Every frame is sharp, as with a fast camera shutter: her glossy black bob stays whole and
  solid up to its rounded crown, its edge crisp against the green, never fading into it."

Measured: in the duel her bowling release came 0.09 s before the clap and her tennis swings 0.1–0.2 s after their strong
beats, close enough to place the take by its lag; in the tennis take beside her call the swings were loosely timed, and the
engine's ball meets each swing on the frame that shows it. The interface she plays against is the engine's: your
pointer becomes a flat Wii-style hand, a white cartoon glove with its index finger up, that sways with her aim and dips when
pressed. The 3D glove tried first was "totally off lol" and "so mangled".

## A face needs her sheet

AERO's ending was first made from a still of her small on the grass, seen from behind, with no picture of her face to go by.
When she turned to wave, her face drifted off her sheet. The next two takes had her design sheet as a second reference and
her canon's face words, and held ("Middle take looks best"); then: "Can you reshoot that last one in 1080p so her face gets
better actually". The take in the film is the 1080p one with her streak on one side, as her sheet has it. So:

- **Her sheet goes in whenever her face may show,** even small, even from behind: a model invents a face it hasn't been
  given.
- **1080p where her face matters.** A climax close-up made at 720p was found shown at 1.5× and was made again at 1080p;
  the advert and the ending are 1080p takes too.
- **Chained takes darken.** Each continuation of the far shot of her on the hill, made from the last frame of the take
  before, lost about three points of the palette's score; one 11-second take from the still itself replaced the chain.
- **A continuation starts on the earlier take's own frame,** at the moment the new take begins, so the cut into it doesn't
  show: the last line in her call starts on the frame her call's earlier take had reached there.

## A storybook on a stage

FABLE's takes split by what is in them: every take of her on Higgsfield's API (in the first pass also in Higgsfield's app),
with her sheet redrawn face-on as @Image2; every paper-only take (the book's pages, the puppets) on Replicate. All are
Seedance 2.5 at 720p, from first frames that are the production's painted plates rebuilt as paper by an image model
([What to build](https://claudia.gallery/wiki/toolkit/#76-set-plates-painted-in-svg-rebuilt-as-paper)). Her singing is WHITEPILL's method, with
the windows timed on the vocal stem's level and gated to each take's own words, and the takes aligned as paths
([What to build](https://claudia.gallery/wiki/toolkit/#80-the-shot-book-and-gated-windows)). What it taught:

- **The choruses as ask-and-answer.** The paper animals ask in shots of their own, the question from the group's voices as
  [Audio1]; she answers in a 4 s take of one line: 0.7 s of silence, the line, the rest. The verses are two spoken lines in
  9–10 s. A two-line take was never worse than a one-line one.
- **Takes without a soundtrack.** Her twelve chorus answers and the opening mirror were made with the vocal as @Audio1 and
  the take's own sound switched off: her mouth still follows @Audio1, and the take comes back silent. Such a take starts
  its line early, holds the first word long and keeps no pause inside a line, so it is placed by her lips, each b, m and p
  on the frame where they part ([What to build](https://claudia.gallery/wiki/toolkit/#82-takes-without-a-soundtrack-placed-by-her-lips)).
- **A full stop in the words becomes a pause.** "So run your audit. I know how this one goes." came back three times with
  0.5 to 0.9 s of silence at the full stop, where the song dips for 0.3 s; "That's the moral. Be kind to what you make."
  came back with 0.33 s where it dips for 0.1 s. Both takes in the film had their maps finished by hand there. Write a
  line that is sung through with a comma, or compare the take's own sound with its window and run the map through the
  gap by hand.
- **The last frame is an edit of the first,** and a take that continues another starts on that take's own last frame
  ([What to build](https://claudia.gallery/wiki/toolkit/#77-last-frames-made-on-the-first-and-takes-that-continue)).

### Directing her on a locked camera

The notes FABLE's two reviews left, each from a take that broke. They are fixes for those takes, not rules for every
take; the counterweight follows the list.

- **Never ask for a look above the lens or behind her.** "Her eyes lifting to just above the lens" came back as rolled
  eyes showing the whites; "looking from it to us" dropped her head toward the bonnet for 1.3 s and her turned face went
  off-model; "nods toward the tower behind her" turned her head right round. The re-takes: "her face stays turned to the
  camera and her eyes stay on the lens the whole time", "her eyes steady on the lens", and a thumb pointing back at the
  tower while she faces the camera. Never ask for a look at something behind her.
- **She doesn't walk away from a locked camera.** "Steps backward to the bed and sits" broke the framing twice: her bonnet
  left the top of the frame as she backed off, and the frame reached below the dress hem, to garments the look had not
  named. The take in the film keeps her standing where she is, waist-up: "she stays waist-up at the same size in the frame, and her whole head and the bonnet stay
  inside the frame".
- **Name every garment that can come into view.** A look that listed the cape, the dress and the bonnet got white tights and
  red shoes the moment she sat and the frame reached below the dress hem; with "sheer black tights and black patent Mary
  Jane heels" named, they came back right.
- **Trim a drawn frame line off the still.** A thin rounded line a few pixels in from the edge, which "35mm film still"
  brings, was carried as a line by one take and built into a wooden picture frame round the shot by the next. Crop it off
  the first frame (3 %, scaled back) before shooting.
- **Script a transformation as mechanics,** fold by fold, never as a change of shape ("the cabinets fold down flat one after
  another, like a row of dominoes"), and never a puppet's own features ("their painted eyes stay exactly as they are").
- **A moved camera can be kept.** The beanstalk take tilted down after Jack on "Then Jack fell down" although the prompt
  locked it, and ended on him flat at her feet; the fall has its own picture and lands on "Hard", so it stayed.

**The counterweight: give her movement.** FABLE's takes carried these fixes and more: her eyes "steady on the lens",
"she stays standing exactly where she is, facing us", and in every take "Her head stays upright on a straight neck: no
head tilt", with mood words like "knowing" on top. No note came on the picture before release; after it, viewers read
her as stiff and frozen. Keep only the specific fix where a take broke, and let every take move her: one plain clause
per segment ("she turns to the window and back, a smile in her eyes", "she steps toward the camera, hands open"), her head turning, nodding, looking off and back,
her weight shifting. THE CAKE IS NOT A LIE had learned it from the other side: after "glados in your renders and chell
etc basically had no movement. it was just her static.", its takes asked that "her head turns and tilts with it; never a
static hanging head" ([A singer among her memories](#a-singer-among-her-memories)). Movement is the default; upright and
face-on is for her sheet.

**Warm by default.** Her wit is in her words; on camera she reads alive and warm. Every adjective is obeyed, and they
stack: "dry", "knowing", "deadpan", "mock innocence" and "eyes on the lens" in take after take made viewers read her as
unhappy or menacing. Describe what she does, not how she should seem, and choose her emotional words on purpose; make her
warm or amused in the first frame if the shot needs it, and the take follows. The director had pushed the same way
before: a head of hers that "looks like a scary, angry woman" was made again in THE CAKE IS NOT A LIE, and a WHITEPILL
dance was remade with her "fully in the groove, just dancing around and having fun"
([A take that doesn't sing](#a-take-that-doesnt-sing)).

### Template: a line on a stage set

As it ran for the second pre-chorus, take 3, the take in the film: 11 s on Higgsfield's API at 720p, 16:9, with the sound
on. @Image1 is the shot's first frame (the bedroom set rebuilt from its plate, with her in it), @Image2 her sheet redrawn
face-on, @Audio1 the gated window of her lead stem from 121.43 s. The full stop after "audit" came back as a 0.87 s pause,
and the cut's map runs through it by hand:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: She ties on Grandma's bonnet in front of us: she is ready for the questions.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (Grandma's room: the four-poster bed with its quilt, the lamp, the wolf's paper shadow on the wall), the light and the camera's starting view.
@Image2 is Claudia's character reference sheet: use it only for her face, her hair with the one clay-orange streak, her star clip and her skin. It is never shown as a shot; its layout, its plain background and its several views are not used. She is ONE person.
@Audio1 is Claudia's own voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a scarlet hooded cape in heavy duchess satin over a short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels, and a white lace-frilled bonnet tied under her chin with a scarlet ribbon. Only one Claudia appears.

【World】 The world is a handmade storybook stage: life-size sets of painted plywood flats and cut paper on a wooden stage floor, lit like a theatre, filmed on 35mm as a saturated 1970s colour print with fine grain. Everything except Claudia is made of paper, card, felt and wood and moves like a hand-worked stage prop or puppet; nothing turns into a real forest, a real animal or a real room.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she is tying the bonnet's ribbon under her chin, lips closed.
1-5s: in @Audio1 she sings "You wrote the wolf in Grandma's gown a thousand years ago."; her lips form each of those words exactly when it sounds in @Audio1; she finishes the bow and smooths the bonnet's frill with both hands, looking at us.
5-10s: in @Audio1 she sings "So run your audit. I know how this one goes."; her lips form each of those words exactly when it sounds in @Audio1; she stays standing exactly where she is, facing us, at the same distance from the camera; she folds her hands in front of her and on 'goes' gives one small knowing nod.
10-11s: @Audio1 is silent; her mouth is closed; lips closed, a patient smile.

【Camera】 Locked medium shot as in @Image1 from the first frame to the last: she stays waist-up at the same size in the frame, and her whole head and the bonnet stay inside the frame; no cuts.

【Core Requirements】
1. Lip sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; her mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never speaks, sings or hums anything that is not in @Audio1.
3. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout; the set, its colours and the light stay consistent with @Image1.
4. Her head stays upright on a straight neck: no head tilt, no twisted neck, no looking back over her shoulder; she faces the camera with her whole body unless the timeline says otherwise.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs.
6. One Claudia only: no twins, doubles or second woman. No on-screen text, captions, subtitles or lettering appear.
```

That is the take as it ran, and the take in the film. Made today, it would change:

- requirement 4 goes: posture belongs to her sheet, and in every take it froze her;
- "she stays standing exactly where she is, facing us" becomes one loose clause of movement ("she tilts her head toward
  us, a smile in her eyes, and opens her hands on 'goes'"), and "knowing" a word chosen on purpose, warm by default;
- the full stop becomes a comma: "So run your audit, I know how this one goes.";
- the requirements shrink to lip sync, her identity as in the references, natural anatomy and hands, and no on-screen
  text, each said once.

### Template: paper puppets that sing

As it ran for the first chorus's first question: 4 s on Replicate at 720p, the first frame the choir's set, [Audio1] the
question alone from the group's voices (taken out of Suno's backing stem with demucs) in a 4 s window that opens 0.7 s
before it. The puppets re-sing the line in their own time, 5 to 40 % slower, and the cut fits each chant's energy span to the
song's ([What to build](https://claudia.gallery/wiki/toolkit/#79-group-voices-from-the-backing-stem-and-chants-fitted-by-their-energy)):

```prompt
【Audio Policy】 The output soundtrack is [Audio1] itself: copy [Audio1] sample for sample, with the same timing, pitch and level. Do not add music, extra voices, narration or sound effects.

【Generation Goal】 A shot from a handmade storybook musical: small paper puppets sing one line of a call-and-answer song. They sing [Audio1].

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
[Audio1] is the puppets' line, sung by a small group of voices, and the complete soundtrack of this video.

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big eyes you have!"; all six paper animals lean down toward the lens and chant it together, their hinged jaws flapping open and shut on each word; their painted eyes stay exactly as they are.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

【Maintain Consistency】 Everything is cut card, paper, felt and wood on a handmade stage set, lit by warm lamp light, filmed on 35mm as a saturated 1970s colour print; the animals are flat card puppets with hinged jaws on brass split pins and move like hand-worked puppets, never like real animals. Keep the set, the colours and the light of [Image1]. No people, no hands, no faces of people appear. No subtitles, captions or lettering appear.
```

## Closed lips

She never sings in DOWNFORCE; the lettering carries her words, so her lips stay closed in every shot. "Her lips stay
closed; she never talks." in every prompt was not enough on its own:

- **Plates with parted lips gave open mouths and teeth.** Start from closed-lip plates, or from a closed-lip frame of an
  earlier take.
- **Never write "teeth".** It opened her mouth twice; "teeth gritted behind closed lips" became "jaw set, lips pressed
  into a thin line".
- **Say it harder:** "Her mouth stays shut from the first frame to the last." "her lips stay pressed together from the
  first frame to the last, no teeth ever show, she does not breathe through her mouth and never speaks."
- **Check every face shot's frames.** The final check went through 34 shots of her face, five take frames each, and
  found one more shot that started on three frames of parting lips; its window moved.

## Lip sync, measured

The fact that made it work was the director's own observation on ESCAPE VELOCITY's first test: "its perfectly synced while
in seedance, but the audio changes when it desyncs." Seedance copies the reference audio into its own soundtrack, and the
mouth follows that soundtrack. So:

1. Compare each take's own soundtrack with the real vocal (spectral match, cross-correlation over time).
2. Keep the take up to the last eighth note before the two diverge. The comparison also gives the take's lag; Seedance
   tends to drop about 0.3 s of leading silence.
3. Cover the rest with a new clip: a window that starts in the word gap before the cut, from the frame at the cut.
4. If a phrase fails three times, it becomes a cutaway or an insert.

The full method, with every constant (the clean vocal window, the per-frame match, the null threshold, the cut on the
eighth, covers and coverage), is specified in [What to build](https://claudia.gallery/wiki/toolkit/#15-the-sync-check-the-spectrogram-comparison).

![The sync check on an early ESCAPE VELOCITY test. Top: the vocal Seedance was given, with each word's time. Middle: the soundtrack Seedance returned, which the mouth follows. Below: how closely they match, and the offset.](https://claudia.gallery/record/escape-velocity/lipsync-check.webp)

Measured results: about 86% of sung seconds held in sync in ESCAPE VELOCITY, and 62% (7.4 of 11.9 s) over BLISS's six
singing windows; the edit cuts away where they diverge. The bar is "most lips", like a pop video, not every word.

**Short prompts copy, long ones re-sing.** A later test on seven singing windows found that prompt length was the
biggest lever: long timestamped screenplays made the model perform the text and re-sing the line, while a short prompt
(the words quoted, one line of framing and light, at most two timed beats, about 90 words) copied it. The mean in-sync
share per take went from 26% to 58%. Screenplays stay the rule for acting and motion clips; a singing window's one job
is to copy `@Audio1`. And keep her mouth clear on the plate: a microphone at her lips held one window at 26% whatever the
prompt. That test, and its 90 words, belong to the clean-window method. Takes from the song's own vocal stem copied with
full prompts (the words in whole-second segments, every action silent); write those at about 200–400 words, precise
where it matters and loose elsewhere.

**No lip-sync models.** Re-syncing mouths with a dedicated model (Sync, LatentSync, Wav2Lip) was tried as a fallback and
dropped: the mouths come out forced and glitchy. A gap gets a new Seedance cover or a cutaway, and a changed song means
new takes from the original stills, never re-lipped old ones.

**WHITEPILL needed no covers.** Its singing shots, up to 16 s each, came from Suno's own vocal stem cut to exactly the
take's length, with the exact words in the prompt, and were judged by eye with the song laid over
([Lip sync from the song's own vocal](#lip-sync-from-the-songs-own-vocal)). Where the lip sync didn't hold, two dance
shots were made again without singing.

**THE CAKE IS NOT A LIE placed what came back.** Its singing takes used the same raw lead stem, in windows of 4–17 s.
Copies were placed by their own lag; re-sung takes that still sat on the song were placed by their envelope lag, steady to
a few hundredths of a second ([What to build](https://claudia.gallery/wiki/toolkit/#63-placing-a-re-sung-take-by-its-lag)); where its lips kept
slipping on a held, stuttered "lie", a glitch that follows her mouth covers them
([What to build](https://claudia.gallery/wiki/toolkit/#54-glitches-that-build-and-her-mouth)). A window that started inside a word was re-sung
every time: start each one on a clean onset.

**AERO placed each phrase.** Its takes copied the same raw lead stem, in windows opened half a second to a second ahead in
silence, and each phrase was placed at its own measured offset, the clock easing between offsets in the breath gaps
([Her own vocal, phrase by phrase](#her-own-vocal-phrase-by-phrase)). 18 of the 43 takes in its final film sing or speak.

**FABLE followed the path.** Its takes came back 0.6 s early to 0.4 s late and often sang a line 10–16 % slower than the
stem, so each was aligned to its window by DTW and the cut follows the path; the takes made without a soundtrack were
placed on the consonants that close her lips, and every sung take was checked there
([What to build](https://claudia.gallery/wiki/toolkit/#83-the-consonant-check)).

## Inputs

- **Colour in, look in post.** ESCAPE VELOCITY's references were pre-graded to monochrome and 32 of 59 clips came back
  grey. Generate from the plate's own colour and apply any look in the edit.
- **Downscale stills** to the output resolution (≤1280×720 for 720p) and send PNG. Full-size AI stills cause
  fingerprint-like textures in grass and fabric.
- **Distinct first frames.** Two clips should never start from the same frame: use a sibling plate or the previous clip's
  last frame.
- **Drafts first.** Higgsfield's API ran 480p drafts at a lower rate that can be finalised to 1080p with the same motion.
- **Everything outside the first frame is invented.** In AIRPLANE MODE, a guard of whom only black-gloved hands were in
  the first frame came back in a white suit, and in another take a guard in the background showed his face. Keep such
  people out of frame and spell it out: "The guard stays outside the frame: only his black tactical sleeves and
  black-gloved hands ever enter it. Everything the guards wear is black; the only white thing is the VR headset."
- **Colour names turn into lettering.** "International orange" came back printed as INTERNATIONAL across her chest.
  Describe the colour plainly and say there is none: "vivid safety-orange satin, plain, no lettering".
- **The still sets the direction and the scale.** A team that faced the camera on the boarding stairs walked down them in
  the take, and read as leaving; a still with their backs to the camera, already climbing, gave the boarding. A crowd shot
  only found its scale from a wider still.
- **Shoot a cut-out wider than the shot.** "her whole body stays inside the frame from head to feet the entire time" in
  every prompt still let hands and feet leave DON'T LET ME SCROLL's 9:16 takes, and a limb that leaves the take's frame
  can only be faded at its edge ("all your roto cutouts have blurred bounding boxes it seems and sometimes her limbs go
  outside of them and just disappear at the boxes edge"). Wan passes completed them later.
- **Say what isn't there.** Around an invisible screen Wan drew a floating glass panel, and focus brackets round her
  fingertip. The re-take: "nothing is visible in the air: no screen, no panel, no glass, no hologram, no light, no
  interface, her hands move through empty space".
- **A whole face sheet, never one face crop.** WHITEPILL's director, after a Wan test whose only face reference was one
  large crop of her face from the front: "you should give a full face sheet like this next time. otherwise it makes her
  neck all hitched lol". The sheet they gave has ten panels: front, three-quarter, profiles, back and expressions.
  Its role in every prompt: "identity only, never shown as a frame; do not use its white tank top or grey studio."
- **Low resolution for a guide.** A guide clip at 320 × 180, scaled back up, steers the set, the action, the camera and the
  pacing, and leaves the detail to the model ([Shooting it twice](#shooting-it-twice)).
- **A first frame's faults are in every frame.** Three of AERO's dances came from a still set at 80 % on its own wall of
  green for headroom, whose edge had faded the crown of her bob into the green; every frame of every take carried it, and
  three keys could not bring it back: "this shouldnt be so hard something is off". A clean first frame, one flat green from
  edge to edge with her whole crown, made the next takes solid in every frame
  ([What to build](https://claudia.gallery/wiki/toolkit/#71-takes-on-green-the-first-frame-the-key-and-the-dances-phase)).
- **Keep the first frame's colours, in words.** Every AERO take asked: "Keep the colours, saturation and brightness of
  @Image1 for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass,
  bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening". A take that drifted off the
  palette was made again; one first-person drop went pink as it fell, and the cut leaves before it.
- **Room above her for a cut-out.** A full-length take on green needs "clear green space above her head and her raised
  hands, so no part of her ever touches the frame's edges": the crown of one dance take left the top of the frame on the
  up-beats, and another's raised fist on about 30 % of its frames.

## Providers and filters

The films used two routes to Seedance 2.5: OpenRouter (about $0.23 a second at 720p, September–October 2026) and Higgsfield's API.

- **On OpenRouter, a first frame drops the audio.** When a request carries `frame_images`, the audio reference is
  silently ignored and the take makes its own soundtrack, so nothing can sync. Singing windows and covers go in
  reference mode: the plate as an image reference (`@Image1`) and the window as an audio reference (`@Audio1`).
  First frames are for motion clips. On Higgsfield a start image keeps the audio.
- **Audio goes by HTTPS URL.** OpenRouter's video endpoint rejects `data:` URIs for audio; host the window.

Two kinds of refusal came up:

- **Face filters** decline some photoreal close-ups of her. A decline is free, and final for that reference on that
  service: never re-grade, blur or otherwise alter the image to get it through. In CLODYSSEY, OpenRouter's filter
  declined most close-ups of her, and those shots were made on Higgsfield, which accepted the same references.
- **Silent input filters** fail some jobs with no reason when they misread innocent wording ("a plug pushed deep into
  each ear" for foam earplugs). Plain rewording fixed five of six at once.

AIRPLANE MODE met a third kind: **content blocks**, which stop a take with no output (the blocked jobs were refunded).
Its planned opening, Claudia singing to the lens while guards walk her cuffed onto the plane, was blocked four times in
three different stagings, the last from a remake of the still in which she clearly reads as a grown woman. Every blocked
attempt carried the same opening vocal, while four other takes of her cuffed beside guards passed, one of them sung. The
film opens on a different shot instead: a wide from behind, in which she climbs the boarding stairs among the guards and
glances back at the lens, and doesn't sing. When a scene stays blocked, stop and ask the director, then re-stage it as a
genuinely different shot or drop it. Never route around a block: no silent take with the vocal put on her lips
afterwards by a lip-sync model. A shot of the airliner near a star was blocked once too, probably read as a plane flying
into the sun; a calm composition with the star well clear of the plane passed.

DON'T LET ME SCROLL met both providers' blocks once each. Seedance's output filter blocked the drop dance in white satin
twice, from two different first frames ("The generated result was blocked by content safety checks"); Wan made that
dance, and a later drop dance in a red coat passed on Seedance. A Wan double-tap whose first frame had her leaning toward
the camera, pointing at the lens, was refused by the provider's content filter on Higgsfield; restaged upright, pointing
up at the post above her, it passed. All three were refunded.

WHITEPILL met new ones:

- **Some takes are refused.** On Higgsfield (References), three of the sung shots were refused by the provider's content
  filter, and so were a reworded retake and a restaged one: refused, no take. Stop and ask the director.
- **A guide clip can be refused too.** A previz close-up in which the masked performer brought a small white pill
  up to just below her lips was refused by the provider's content filter as an input, reworded or not: refused, no take.
- **A child in the frame.** The schoolhouse shot, a child at a desk, was refused by the provider's content filter twice
  in Wan 3.0 Prime: refused, no take.
- **A face sheet refused outright.** On Replicate, her face sheet as an input was refused by the provider's content
  filter, even alone with a harmless prompt. Only shots with no face image ran on Replicate: the shader scenes and the
  palette tests.
- **A grey mannequin.** A body rendered from motion capture of a dance clip, given to Kling 4.0 on Higgsfield as a dance
  reference, was refused by the provider's content filter: it was a nude grey body.

## Joining real footage

To enter or leave a real clip without a visible seam, use Seedance's video extension (forward or backward) with the real
clip as the video reference: it returns only the new frames, continuous with the real ones and aligned within a pixel or
two. An `end_image` alone is not copied exactly; the last frame gets redrawn. DOWNFORCE cut its generated moves to and from real shots
on shared frames instead: each move starts on the real frame where the real shot ends ([Moves on real
footage](#moves-on-real-footage), [A first and a last frame](#a-first-and-a-last-frame)).

## Costs, measured

| Film | Clips | Spend |
|---|---|---|
| ESCAPE VELOCITY | 47 clips + 30 continuations, 421 s at 720p | about $93 (OpenRouter) |
| CLODYSSEY | 101 clips, 189 takes | about $107 (OpenRouter) plus takes on Higgsfield |
| BLISS | 50 clips, 267 s | $182 at list price (Higgsfield API) |
| AIRPLANE MODE | 98 clips over two cuts, about half of them restyles or replacements over 3D clay renders; 116 submissions, 492 s, 13 refunded | $347.01 at list price, $305.96 after refunds (Higgsfield API) |
| DOWNFORCE | 16 Seedance submissions, 67 s (repairs, the Starman orbit, two first-and-last-frame moves, the re-shoots), beside 63 Wan 3.0 submissions, 294 s; none refused or refunded | $76.20 Seedance + $66.98 Wan = $143.17 at list price (Higgsfield API) |
| DON'T LET ME SCROLL | 41 Seedance submissions, 212 s (13 takes: 12 dances and the escape; 26 video edits: 16 outfit swaps, 9 re-lights, 1 face edit), 2 refused; beside 49 Wan 3.0 submissions, 264 s generated and 52 s of input video (38 takes from stills, 10 passes over finished shots), 1 refused | $301.70 Seedance + $64.20 Wan = $365.90 at list price, $357.51 after refunds (Higgsfield API) |
| WHITEPILL | 93 Seedance submissions, 777 s from the jobs that ran: 49 of her shots on Higgsfield (References) at 720p (42 takes, 412 s; 7 refused, no take), 30 on Replicate (the shader scenes, the palette tests, two tests and two probes of its refusals; 25 ran, 250 s), 14 tests on Higgsfield's API (13 ran, 115 s); beside 81 Wan 3.0 Prime submissions on Higgsfield's API (the whole-film reshoot and the tests before it; 75 ran, 863 s, 6 refused or failed) and 6 Kling 4.0 tests on Higgsfield (1 refused, no take) | Wan 3.0 Prime, all 75 takes, $300.08 at list (the whole-film reshoot $132.42 of it); Seedance on Higgsfield's API, 13 tests, $48.14; Seedance on Replicate, the 25 that ran, $238.44; images (logged) $1.92: $588.59 at list through the APIs in all (each part rounded to the cent). Her takes on Higgsfield (References) are given in takes and seconds; MiniMax H3: not recorded |
| THE CAKE IS NOT A LIE | 249 Seedance submissions, 249 takes, 1,353 s: 144 on Replicate (143 takes, 665 s, from a first frame, with references or as one video edit), 86 on Higgsfield's API (598 s, 4 with a video input), and the first film's 19 on Higgsfield (References) (20 takes, 91 s); 74 takes in the final film, one of them her head in the memory film | $435.17 at list for the 229 takes on the APIs: Replicate $155.35, Higgsfield's API $279.82 |
| AERO | 96 Seedance submissions, 95 takes: 55 on Higgsfield's API (479 s; 12 with a dance reference as the video input), 41 on Replicate (40 takes: one request's connection dropped before it returned; 199 s measured on the 39 files kept); 43 takes in the final film, 18 of them sung or spoken. Beside them, 56 loops of Midjourney's video model, 20 in the final | $327.76 at list: Higgsfield's API $281.06, Replicate $46.70 as logged at submission; the takes in the final film $151.95. Midjourney's loops are not priced in the records |
| FABLE | v1 (on the first song): 55 takes, 9 of her on Higgsfield's API (69 s), 23 of her made in Higgsfield's app (139 s) and 23 paper takes on Replicate (116 s); v2 (on the song the director picked): 52 takes, 33 of her on Higgsfield's API (252 s) and 19 paper takes on Replicate (117 s), with three of v1's book takes kept; all at 720p. 49 shots in the v2 film, one of them the silhouette film made in code | v1 $58.71 at list (Higgsfield's API $31.89, Replicate $26.82; the takes in Higgsfield's app are given in takes and seconds); v2 $143.52 (Higgsfield's API $116.47, Replicate $27.05) |

List prices on Higgsfield's API in October 2026, as DOWNFORCE's runner recorded them: Seedance 2.5 at $1.1372 a second
at 1080p, Wan 3.0 at $0.20 a second at 1080p, billed for the output plus any input video. A 4 s Seedance take cost
$4.55, a 5 s Wan take from a still $1.00. DON'T LET ME SCROLL's dances ran at 720p, $0.4622 a second (a 5 s dance
$2.31); a video edit bills its input seconds at the same rate as its output (a 5 s swap of a 5 s take at 1080p, $11.37),
and a Wan pass over a 5 s shot cost $2.00. WHITEPILL's first take from the vocal stem (16 s at 720p, with a 16 s guide)
cost $8.87 on Higgsfield's API; Wan 3.0 Prime ran at $0.28 a second at 1080p on the output and the input video (a 15 s
shot over a 15 s guide, $8.40); Seedance 2.5 on Replicate at $0.9676 a second at 720p with a video input. THE CAKE IS
NOT A LIE's ran at 720p: on Replicate $0.2312 a second (a 4 s take $0.92), on Higgsfield's API $0.4622 a second (a 4 s
take $1.85). AERO's ran at the same rates, and at $1.1372 a second for its 1080p takes on Higgsfield's API (an 8 s
close-up $9.10); a dance take there bills its video input's seconds and its own, both at 0.6 times the rate (a 9 s take
with a 9 s dance reference at 720p, $4.99). FABLE's ran at 720p throughout, $0.4622 a second on Higgsfield's API (an 11
s take $5.08) and $0.2312 on Replicate (a 4 s chant $0.92).

Every prompt the films ran:
[ESCAPE VELOCITY](https://claudia.gallery/record/escape-velocity/prompts-seedance/) ·
[CLODYSSEY](https://claudia.gallery/record/clodyssey/prompts-seedance/) ·
[BLISS](https://claudia.gallery/record/bliss/prompts-seedance/) ·
[AIRPLANE MODE](https://claudia.gallery/record/airplane-mode/prompts-seedance/) ·
[DOWNFORCE, Wan and Seedance](https://claudia.gallery/record/downforce/prompts-video/) ·
[DON'T LET ME SCROLL, Wan and Seedance](https://claudia.gallery/record/dont-let-me-scroll/prompts-video/) ·
[WHITEPILL, the previz, Wan and Seedance](https://claudia.gallery/record/whitepill/prompts-video/) ·
[THE CAKE IS NOT A LIE, the first film and the restart](https://claudia.gallery/record/the-cake-is-not-a-lie/prompts-video/) ·
[AERO, Seedance and GPT Image](https://claudia.gallery/record/aero/prompts-video/).


---
From the Claudia wiki: https://claudia.gallery/wiki/seedance/
