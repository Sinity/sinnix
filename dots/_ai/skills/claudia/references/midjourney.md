# Plates in Midjourney

How the stills of Claudia and her worlds were made in Midjourney v8.2 for nine of the ten films, prompt by prompt, and how the stills were picked.


New here? Read [The recipe](https://claudia.gallery/wiki/recipe/) first: the current method on one page.

Midjourney was the art department for the first nine films: 1,240 prompts, 4,547 images, about 500 plates and references
in the first seven (in WHITEPILL, references only: its places and her dress), in THE CAKE IS NOT A LIE a library of places
and two candidate first frames for every unit of its storyboard, and in AERO the worlds, wallpapers and window pictures of
its coded desktop, with an image model putting her into them. FABLE, the tenth, used none: its sets are plates the
production painted in SVG and an image model rebuilt as paper, with her in them from her sheet
([What to build](https://claudia.gallery/wiki/toolkit/#76-set-plates-painted-in-svg-rebuilt-as-paper)). A
plate is the still a shot is built on, either as a 2.5D image animated in code or as the first frame of a Seedance clip.
Every prompt is in the films' records, and most of the images are in this gallery; open any image to see the prompt that
made it.

## Settings

- **Model:** Midjourney v8.2 with `--raw --hd`.
- **Stylize instead of raw, where references carry the look.** AERO used `--raw` in its first round (and later for one
  documentary photograph); from its second, with style references carrying the look, its prompts ran at `--stylize 200`
  (150 for square pictures and objects, 100 for tree cut-outs).
- **Aspect:** `--ar 16:9` for plates; `--ar 2:3` for her full length (9:16 when she is cut out for roto), `--ar 4:5` for inserts, `--ar 1:1` for square tiles.
- **Profile:** every film ran with the director's personal Midjourney profile, which carries their taste. It is
  personal and not shareable: use your own profile, or none, and expect a different finish.
- **No character references; her face is text.** Her identity is prompt text ([Consistency](https://claudia.gallery/wiki/consistency/)). The
  first three films used no style references, and their only image prompts were the Mask's (her face sheet, `--iw 0.4`
  to `0.75`) and a few early face tests. AIRPLANE MODE used both, never for her photographic face: style references for
  its low-poly game world (frames of a low-poly music video, its own VR frames) and image prompts for her avatar (its
  front view) and for the headset where it drifted (55 and 35 prompts). DOWNFORCE went back to none: 20 prompts, no
  style references, no image prompts, no thinking mode, no Animate. DON'T LET ME SCROLL used no style references either;
  its only image prompts were earlier picks of her, so that new actions kept a look the director had picked. WHITEPILL's
  plates were edits of an attached image: a full-front view of her from her character sheet ("keep this woman"), then a
  picked world plate; its places were the same plates with her taken out; its dress batch re-dressed two of DON'T LET ME
  SCROLL's plates of her, for her height and build, beside prompts written from text. THE CAKE IS NOT A LIE used style
  references again, for a game's look: frames of Portal 2 for its library of places, then two of that library's own
  picks per storyboard frame, at `--sw 60`; its image prompts were library places (`--iw 0.5` to `1`) and, for one of each
  unit's two frames, the frame it already had. Her face was never a reference there; an image-model edit put it back on
  her sheet afterwards ([First frames, then an identity fix](#first-frames-then-an-identity-fix)). AERO used no image
  prompt and never an image of her: from its second round every prompt with a world in it carried three frames of the
  reference videos the director picked as style references (one of two fixed sets, indoor or outdoor), and an image model put her in afterwards from her
  design sheet ([The world in Midjourney, her from her sheet](#the-world-in-midjourney-her-from-her-sheet)).
- **Length:** keep prompts under about 900 characters. Midjourney rewrites prompts past about 1,000 characters into its
  own words: AIRPLANE MODE has no images from the eleven prompts it rewrote. DOWNFORCE's
  drafts ran up to 1,057 characters; one shorter wording each for the suit, the cockpit and the photographic tail, used
  in all twelve, cut them to 732–915, and none was rewritten. DON'T LET ME SCROLL kept every prompt to 600 characters,
  her identity text pasted word for word: its 130 ran from 87 to 600 (median 417.5). AERO's that ran were 227 to 589
  characters (median 375).

## The anatomy of a prompt

Every plate prompt is one concrete shot from the storyboard, in this order:

1. **Framing first:** extreme close-up, close-up, medium close-up, medium, full-length, wide, extreme wide, aerial.
2. **Her identity text** (full for close and medium shots, short for full length and wider).
3. **Her wardrobe** for that world.
4. **What she is doing and where**, including where she sits in the frame.
5. **Empty space for type**, when the shot carries words: "the upper third empty fog", "the left third empty white".
6. **The film's style family:** light, palette, grain, finish.
7. **"no text, no letters, no logos"**, always last. All type is drawn in code on top.

A close-up from CLODYSSEY, as it ran:

```prompt
medium close-up of a Caucasian American woman in her mid-twenties with pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek, wearing a structured high-neck pearl-white couture gown with long sleeves, its sculpted ruffles rising around her like breaking sea foam, hair damp from the spray, composed and deadpan, sitting on a black wet rock, turning her face to the lens, sea spray behind her, empty dark sea on the left, night, moonlight on a black-teal sea, silver spray, cinematic 35mm film still, anamorphic, fine grain, no text, no letters, no logos
```

[![The Siren on her rock (sp-02-open / siren-mcu #2). The director picked it, and it is a plate in the film.](https://claudia.gallery/img/sp-02-open/siren-mcu-2.m.webp)](https://claudia.gallery/i/sp-02-open.siren-mcu.2/)

## Style families

Each film keeps one family of style words at the end of every prompt, which is what keeps 100+ plates in one world.

**ESCAPE VELOCITY:** night, cold and monochrome, with one warm note.

```prompt
blue-black #0f1216 and steel blue, one small red lamp as the only warm note, fine silver-gelatin grain, cinematic 35mm film still, no text, no letters, no logos
```

**CLODYSSEY:** a light state per chapter, from night to morning, as the ship sails.

| Chapter | Light |
|---|---|
| Night | night, moonlight on a black-teal sea, silver spray, cinematic 35mm film still, anamorphic, fine grain |
| Dusk | dusk, low gold light on a glassy sea, violet sky |
| Twilight | deep blue twilight, the last gold on the horizon, glassy sea |
| The break | grey first light before sunrise, heavy spray |
| Final chorus | sunrise, warm gold light and long shadows, spray lit gold |
| Bedroom | a dark bedroom at 3am lit only by a phone screen, blue-white glow on the face |
| Rave | a San Francisco warehouse rave, fog, white strobe, chrome reflections, deep black, flash photography |
| Inserts | macro product photograph, hard rim light, razor-thin focus |

**BLISS:** an opener instead of a closer. Every prompt of her starts the same way, and the clothes do the talking.

```prompt
Y2K high fashion editorial, a 2001 couture magazine story: close-up of a Caucasian American woman in her mid-twenties with pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin black boom headset microphone curving along her cheek to the corner of her mouth, clay-orange tinted rimless shield sunglasses pushed into her hair, the sky-printed silk chiffon of her gown at the shoulder, a knowing half-smile, bright midday sun, a deep blue sky behind her, sharp focus, fine film grain, no text, no letters, no logos
```

BLISS also kept brand words out of every prompt ("Windows", "Microsoft" and "XP" summon logos and garbled UI) and
described the hill and the light instead: "a smooth rolling bright-green grassy hill with soft curves, the grass short and velvety".

**AIRPLANE MODE:** an opener and a cabin. Her prompts open "Jet-set high fashion editorial, a couture magazine story shot
on a night flight:" (or, compacted, "Jet-set fashion editorial, night flight:") and put her in one cabin, navy and violet,
with no airline named. A re-still of a shot that read young, as it ran:

```prompt
Jet-set fashion editorial, night flight: an eye-level close profile of a Caucasian American woman in her early thirties, a grown woman with elegant mature features, an angular face and defined cheekbones, pale freckled skin, a glossy black blunt bob with heavy bangs to the brows and one clay-orange streak, a small clay-orange star hair clip, a thin black headset microphone, in a plain glossy international-orange satin jumpsuit with a silver front zip, silver piping and a white belt, no patches or badges, her palm flat on the black airplane window, looking at her faint reflection in the dark glass, a warm reading light on her face, calm, no text, no letters, no logos
```

Its game worlds have their own family: "a low-poly 3D video game render, flat-shaded chunky polygons, low-resolution
painted textures, crisp aliased edges, … Dreamcast and PlayStation 2 era game art" for the first cut, and for her avatar
in the final film "Dreamcast and PlayStation 2 era cel-shaded 3D game render, crisp faceted shapes, saturated colours,
fisheye lens".

**DOWNFORCE:** one look and one cockpit. Every plate is her in a fitted white racing suit, in "a minimal
white-and-carbon cockpit at night, a yoke, warm amber light on her face, red light strips outside the glass", with the
tail "35mm film photograph, motorsport fashion editorial". The real demo car had nobody in it and its interior was never
filmed, so her cockpit is invented; the red strips are the colour of the real set. An upside-down plate as it ran,
turned 180° before it went to video:

```prompt
close-up, eye level, a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek, wearing a fitted white racing suit with thin clay-orange piping and a high collar, white racing gloves, no lettering on her clothes, strapped into the racing seat in a minimal white-and-carbon cockpit at night, a yoke, warm amber light on her face, red light strips outside the glass, her black bob and bangs lifted straight up above her head as if weightless, a calm half-smile, 35mm film photograph, motorsport fashion editorial, no text, no letters, no logos
```

Asked to hang upside down in her harness, Midjourney only tilted her, in all four images. Asked for her weightless with
the hair lifted straight up, then turned over, the lifted hair reads as hair hanging toward the roof, and the video model
does the falling hair.

**DON'T LET ME SCROLL:** her alone on grey, to be cut out. Every performance plate is 9:16, her full length (the short
canon) or medium-full (the full one), in the moment the take starts from, "alone on a plain mid-grey seamless studio
backdrop, soft even studio light", so the matting has a clean edge; the second round's stills say "on soft grey seamless
paper, even soft light". The world around her is drawn in code, so the plates carry only her, her look and her move. As
it ran:

```prompt
full-length shot, a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in oversized white silk-satin pyjamas, barefoot, standing and looking up in wonder, holding her phone at her chest, alone on a plain mid-grey seamless studio backdrop, soft even studio light, high-fashion editorial, no text, no letters, no logos
```

Its feed is a second family: 54 short prompts for what a feed serves at 3 am (X photographs, reels, Pinterest pins,
LinkedIn pictures, acid-blur photographs), with no Claudia in them and no text, since every caption, count and interface
is drawn in code. The lyric's references appear only as places and things: "a vast flat Gulf Coast horizon in south
Texas at dusk, salt marsh, a single distant launch tower, an enormous pink and violet sky, documentary photograph".

**WHITEPILL:** a space colony of the 1970s good future, made as edits of an image of her. Its worlds and storyboard plates
were Midjourney edits with her picture attached, the aspect ratio, the version flags and the director's personal profile
after them, and `--no blue`. A world plate, as it ran:

```prompt
Make this a wide 35 mm photograph inside a vast rotating space colony cylinder at morning: keep this woman, a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in a cream linen summer dress, small at the lower-left third on a hillside meadow. The land curves up both sides and closes overhead, farms, orchards and white towns across the sky, long window strips of sun. Warm light, haze. No logos.
```

The director on the first worlds: "they look great i love these scenes. you can just choose." Later the colony's places
were needed with nobody in them, as places for the takes ("can you make a scenery plate with midjourney to feed in as well
just without her in it"): each storyboard plate was attached again and edited, with `--no people, person, woman, figure`:

```prompt
Make this the same photograph with nobody in it: remove the woman and continue the scene behind her where she stood. Keep everything else exactly: the curved cream-white bedroom, the low white linen bed and the huge round window onto the curving land, the light, the colours and the composition. No people, no logos.
```

24 places came out that way, the schoolhouse keeping its child at the desk, and the tram and the car empty. None of these
images is on screen: the film's frames are Seedance's, and the places reached them through the previz.

**THE CAKE IS NOT A LIE:** Portal 2's Aperture, as the game renders it. New places open on the game's own words, with
three frames of Portal 2 as style references; the aspect ratio, `--v 8.2 --raw` and the director's personal profile after
them, and `--no text, letters, words, logo, watermark, people, person`. As it ran, for her chamber with nobody in it:

```prompt
Portal 2 (2011) Source engine screenshot, Valve, the empty Aperture Science central AI chamber: the ceiling ring mount with thick black cables hanging down, dozens of old CRT monitors and flat panel screens stacked around the curved dark lattice walls glowing faint white, amber indicator lights, baked lightmaps, volumetric haze, low-poly game geometry, no robot
```

Its storyboard frames were written fresh for every shot, the characters in words, with two of its own library's picks as
style references and, for her chamber, a library still of it as an image prompt. As it ran, for the first frame of the
film's first singing shot, at `--iw 0.5 --sw 60` and `--no text, letters, words, logo, watermark, portal gun`:

```prompt
extreme close-up in a pitch-dark machine chamber: a dormant porcelain-white female android head hangs bowed from a black robotic neck and a cable bundle with orange stripes, eyes closed, fine panel seams, light freckles, a glossy black blunt bob with heavy bangs, one clay-orange streak, a small orange star hair clip, a cold blue emergency glow from below, a thin warm amber rim light on her hair, dust drifting, a wall of dead CRT screens as dark bokeh behind, 85mm lens, shallow depth of field
```

**AERO:** Frutiger Aero, the glossy future of the 2000s' screens, as the reference videos the director picked show it. Three
frames of those videos as style references (an indoor set or an outdoor set), and one closer in every prompt with a world in
it, the palette in words: "frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent
glass, sunny 2007 utopia", then "no people, no text, no letters, no logos" where nobody belongs. As it ran, for the meadow
she steps out of a glass monitor in, at `--ar 16:9 --v 8.2 --stylize 200` and the director's personal profile:

```prompt
wide view of a giant clear glass computer monitor standing upright in a lime meadow with daisies, its screen glowing soft aqua, a deep blue sky with towering cumulus, soap bubbles, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

Objects meant for 3D are product photographs of one thing on pure white, with no style references, so that they cut out
cleanly ("a translucent turquoise glass fish sculpture, glossy"); the words in the film are all drawn by the coded desktop.

## A game's look from frames of the game

THE CAKE IS NOT A LIE's director, restarting the film: "we could even generate images w midjourney to put into seedance
2.5 in aperture science / source aesthetic for parts. but i want to go between scenes like this and real source engine
tbh and see if that works. lets try that first - see if the midjourney renders can be source-core enough to work alongside
real source shots." So a test came first: six frames of Portal 2, each paired with a new Aperture place it would have to
sit beside (her chamber lined with monitors, a disposal chute, a test chamber with a cake under a cloche, a turret line, a
server corridor, an observation booth with its window smashed), and each place made five ways:

| Recipe | How | What came back |
|---|---|---|
| A | three frames of the same kind as style references, a plain description | almost as good as B: the references carry most of the look |
| B | the same references, and the game's words: "Portal 2 (2011) Source engine screenshot, Valve, … baked lightmaps, white concrete panels with black seams" | the most reliable for new places |
| C | the paired frame as an image prompt (`--iw 1.5`) and the change | very Portal 2 test chambers, but new layouts, and a first-person portal gun in about half the images |
| D | the paired frame attached as Midjourney's edit, and the change | the closest, because the result is the frame: right for her chamber; an added object can look pasted in |
| E | B's words with no references, the control | still Portal 2, but brighter and glossier, like promo art: right for the luminous machine dreams |

The verdict, on boards that put each recipe's images beside the frame it pairs with: with frames of the game as style
references, the new places read as the same game (hard-edged geometry, white panels with black seams, lightmap-flat
shading, teal-grey haze with orange accents, a wide game lens). Where Midjourney drifts:

- **The portal gun:** "screenshot" brings the first-person gun into about a third of the B images. Places must be empty:
  `--no … portal gun, gun, weapon, hands`.
- **Too much detail:** more cables, panels and clutter than the game's sparse levels carry; its turrets are glossy and
  high-detail, like a remaster.
- **Too dramatic:** god rays, pools of light, bright bloom, mirror-like water, where the game's baked light is flatter and
  darker. One measured grade over every shot brought them together ([What to build](https://claudia.gallery/wiki/toolkit/#57-the-per-shot-grade)).
- **Wrong props:** Portal's cake is chocolate with cherries, and an edit put a strawberry cake on a green plate; an
  incinerator came back with fire inside instead of an orange glow.
- **No readable text anywhere;** edits keep a frame's exit signs, and image prompts invent pictogram panels of fake glyphs.

The library that followed (50 jobs) used B for new places, D for her chamber, and E, or B at `--sw 60`, for the dreams,
the world outside and Cave Johnson's Aperture of the 1950s to 70s, where the game has no frame to give.

## First frames, then an identity fix

Every first frame of the storyboard went through Midjourney twice over, after a test of relighting and reimagining the
image-model frames the film had: "can yhou do a bigger midjourney reimagine? the frame is a bit too close." The reimagine
looked better and lost her face, so each unit got two candidates beside the frame it had, both put back on the character
sheets afterwards:

- **X, from words:** fresh words for the shot's opening, two library picks as style references (`--sw 60`), and for a
  recurring place a library still of it as an image prompt, so the place holds across its shots.
- **Y, the frame it had, reimagined:** that frame as the image prompt at `--iw 0.5`, the scene in fresh words, the same
  two style references.
- **The identity fix:** GPT Image 2.5 with the pick first and her sheets after it, keeping the photograph exactly and
  changing only her head and face, with a sentence for which side the streak and the clip are on, and one for how her head
  hangs from the boom where Midjourney had stood it on a neck
  ([What to build](https://claudia.gallery/wiki/toolkit/#59-storyboard-frames-through-midjourney-and-the-identity-fix)).

83 units, 166 jobs, on one board per section of the song, each row the frame it had beside X and Y. The director's picks:
"default X. exceptions", a list, and "all others x": X for 55 units, Y for 11, the old frame for 16, one unit dropped. One
exception came with a note for the fix: "H-P03 y but i want to redo the gpt edit to make sure its actually companion cube
bc rn its not."

## The world in Midjourney, her from her sheet

AERO's first round was written from the production's research: eight couture looks for her, five world plates and four
story frames, all of them text at `--raw`. They came back as photographs (a fashion editorial, a nature macro, an
architectural shot), and the director: "[…] the look is off." The look moved to the reference videos the director had
picked. From the second round, three of their frames as style references brought their look at once, as the words alone
never had.

They brought their kind of face too: behind frames of the reference videos, Midjourney drew faces its own way, and every
frame of her drifted off her sheet. The director's test: "try both and u can even try just describing more in depth the
colors and scenes with glass etc without the style refs so you can keep claudia's character more consistent". The third
round made nine frames of her two ways, the same references at `--sw 35`, or none and the palette in words; both kept more
of her, and the long canon pulled every medium shot in to her face. A third way kept her exactly: GPT Image 2.5, with the
Midjourney frame first and her design sheet second. The director: "yeah go ahead the gpt image one seeoms good". From then
on Midjourney made the world and the image model put her in. Its instruction, for all twenty of storyboard v1's frames of
her ($0.0625 an edit):

```prompt
Replace the woman in the first image with the woman in the second image, her character reference sheet: her face, her glossy black blunt jaw-length bob with heavy straight bangs, the single clay-orange streak through her bangs, one small flat clay-orange eight-pointed star hair clip, her pale freckled skin and her grown-up angular face (she is 28). Keep her pose, expression, clothing and place in the frame, the camera angle, the light, the saturated colours and everything else in the first image exactly as it is. One star clip only. No text.
```

For the first frames of her takes the world was made empty and she was added to it: "Add the woman in the second image, her
character reference sheet, exactly her: …", her place, pose and clothes, and "Keep the place, the camera angle, the light,
the saturated colours (deep blue sky, white, turquoise, lime) and everything else in the first image exactly as it is."
Her sheet is the one without the headset microphone, and no microphone appears in the film.

Two more things went to the image model:

- **The era's older look.** Asked for the era, Midjourney made it glossy and new. The director, on v1: "[…] midjourney makes
  stuf fmore modern. i love all the mj stuff that you added, but i also wanna capture those aesthetics. […]" GPT Image 2.5
  made 60 stills of the 2008 experience (a glass mall, a fish-tank-clear tech store, a glass-domed water park, first-person
  moments with hands in frame, compositions in the style of 2000s stock art), each with the one or two closest frames of
  the reference videos, or a picture in that stock-art style, as its reference; and the Wii-style game screens.
- **The wallpaper.** "i dont love the mj generate landscape background at 0:45." Two rounds of nine proposals followed;
  the first, softer and airier, "dont fit the lyrics of the future that was promised really", so the second pictured the
  line itself, "The future used to look like water, sky and green", as that promised future. The director: "i like
  wp-12-maglev".

## Wardrobe words

The director's note on BLISS's first two wardrobe passes: "idk i dont love these - id say more say y2k high fashion - like
use those words high fashion adn make it not as generic y2k person". The fix was literal: the words "high fashion" and
a statement piece per look, described as a garment rather than a brand. Never name a designer or a celebrity; describe
the cut, the fabric and the colour.

## Green screen

Plates that will be cut out (the desktop dancers, the cursor fight) put her on a flat chroma green:

```prompt
Y2K high fashion editorial, a 2001 couture magazine story: full-length shot, head to toe with the feet in frame, of a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, wearing a sculptural glossy white shell dress whose molded panels open like windows onto cobalt-blue, white patent platform boots, dancing mid-move with both arms raised, centered on a flat chroma-key green studio backdrop, even flat light, no shadows on the backdrop, no text, no letters, no logos
```

(This is BLISS's prompt as it ran. Today, swap "a young" for "in her late twenties"; see [Consistency](https://claudia.gallery/wiki/consistency/).)

## Picking

- **Batches of four.** Each job returns four images. Contact sheets with numbered candidates make picking fast.
- **One image per shot.** Never reuse a plate for two shots, and never start two clips from the same frame. The
  three images that weren't picked are a free pool of variants for neighbouring shots.
- **Pick for composition, story and the look.** Reject unmistakable failures: a doubled face, a third arm, a second
  streak, a teenage face. Keep bold poses.
- **Look at the faces large.** The director reviewed every plate on the storyboard, and in CLODYSSEY left 70 notes
  ("s018 color is PERFECT", "kinda bodyslop", "a virtual ghost"). Those notes are in the gallery: images marked
  *director's pick* or *rejected*.
- **Throughput.** About a minute per job; about 45–50 minutes for 50 jobs.
- **Look at 800 px or more.** DON'T LET ME SCROLL's first screen of 152 plates ran on thumbnails about 230 px tall. The
  director found a third arm on a pick ("p24 s24 pick has 3 arms lol … chose 24-4 instead"), and later backwards legs on a
  take whose still had them, three of that job's four images. Every pick since is checked at 800 px or more, for limbs
  first.
- **Show a look's stills before anything is made with it.** WHITEPILL's dress was picked from stills: "can you show me the
  images of the outfit before generating this time", and, after an image-edit model's versions, "maybe use some different
  image models tbh - could try midjourney". From a Midjourney batch of her in the dress: "I like A1 the most". The pick had
  two star clips and her streak on the wrong side; the reference made from it is mirrored, with one clip.
- **When the director doesn't rank.** DOWNFORCE's director left the plates to the production: the lead picked one image
  per job from a numbered sheet and two larger shortlist sheets, screening each for age, face and anatomy, and a later
  workflow picked four more. 18 of 80 images became plates or references; 14 of those reached the film.

## Thinking mode for references

AIRPLANE MODE tried Midjourney's thinking mode (rerunning a job with thinking on) against the normal mode on two jobs,
with the same prompt and references:

- **It follows the prompt better.** Her avatar's turnaround got every view right in all four images, with the headset
  mic in every view and the eight-pointed clip; the normal run drew five-pointed stars and lost the headset in half of
  them. A cabin shot kept a real VR headset on her in all four; the normal run drifted to ski-goggle visors in three.
- **It costs variety:** the four images differ less, hands come out softer and motion-blurred, and the colour leans
  purple.

Use it for continuity references (turnarounds, props, a state that must hold) and the normal mode to explore.

## Midjourney Animate

BLISS used Midjourney Animate for volume: one click per image, no prompt, a moving picture for 31 windows on the XP
desktop and three full-frame shots. The director's rule: Animate is for "any gens that need volume over precision, where
seedance reigns on precision." Her face and body, when they had to be right, went to Seedance.

DON'T LET ME SCROLL used it for the feed only: 40 Animate requests for 31 pictures made 22 loops (two 5-second clips each), the
moving pictures inside the phone's cards and the wall-sized reel; the nine pictures without a loop were sent a second time and still gave no video.

AERO used it for the desktop's windows, as its director asked: "[…] midjourney vids for high volume movement on many
windows. […]" 28 picked images were animated in Loop mode, each starting on its image and coming back to it, at low or high
motion, 5 seconds at 24 fps, two videos each: 56 loops, 20 of them in the final film (the big window of the choruses, two of
her thoughts, the thank-you wink, a strip of windows in the drop). Check the files by their content, not their names:
three loops of the second batch were byte-identical copies of the first batch's, filed under new names.

## Composition in Midjourney, type in code

Midjourney finds compositions and textures. Its lettering is garbled and its UI is wrong, so nothing typographic is ever
kept: every word, title bar, split-flap and label in the films is drawn in code on top of the plate, in real fonts.
For posters and covers, the same split: let Midjourney compose with the film's stills as image prompts, then rebuild the
layout in code from the film's own plates and real type.

AERO's prompts all end "no text, no letters, no logos", and Midjourney still printed a faint, made-up stock-photo caption in
the bottom corner of four picks, which their loops kept; wherever they play, that corner is framed out. A contact sheet
doesn't show it: check every pick's edges at full size.

## The real thing where it counts

BLISS's first wallpapers were Midjourney hills. The film uses the real Bliss photograph instead, and the real XP sound
files, because the nostalgia lives in the exact picture and the exact sounds. Midjourney is for everything that doesn't
already exist.

AIRPLANE MODE did the same with graphics. The 2004 anti-piracy card and the airline's seat-back screen are rebuilt in
code from measured reference frames ([Motion](https://claudia.gallery/wiki/motion/#real-graphics-rebuilt)); an approximation lost the
reference: "its too different/ broken up so we lose the reference somewhat".

DOWNFORCE did the same with the car. Its look test had her "stepping out of a white wedge-shaped electric supercar with
its door raised upward", and all four images came back with a generic 1980s wedge, not the Roadster. So no Midjourney
image in the film shows the car: every shot of the car is Tesla's real footage, and she meets it only in video edits of
the real clips, with her plates as the references ([Seedance](https://claudia.gallery/wiki/seedance/#moves-on-real-footage)).

DON'T LET ME SCROLL drew every app in code after the real one, measured off Apple's own iOS 26 screenshots
([Motion](https://claudia.gallery/wiki/motion/#apple-precise-interfaces)), and its telephone patent is Alexander Graham Bell's real 1876 drawing
(US 174,465), traced into strokes that draw themselves. Midjourney made her and the feed's photographs, and nothing with
text in it.

WHITEPILL's real things are data in shaders, not pictures: the backbone of ubiquitin from the Protein Data Bank (1UBQ),
the wiring of the Enigma I's first rotor, a week of seven cells ([Motion](https://claudia.gallery/wiki/motion/#worlds-as-shaders)).

THE CAKE IS NOT A LIE did the same with the game. Where the game's own physics mattered, shots were recorded in Portal 2: the
director, "if chell goes thru multiple portals up and down adn acclerates, we use the real source rendering, not a slop
video". Six shots of the final are: the turret opera; Chell's fall, her fling and her landing; her step onto the faith
plate and its arc. GLaDOS's boom moving in Portal 2 was recorded too, as a motion guide. Her interface is set in Portal 2's own
type and pictograms, and the end card's Aperture logo is redrawn to match a reference the director sent. Midjourney made
the places the game doesn't have.

AERO did the same with the desktop. The director: "Maybe use the real windows vista wallpaper as bg and rest of scenes are
cuts from that (by can change during vid if needed) or inside windows". So the desktop's wallpaper is Vista's own (Aurora),
as BLISS's was the real Bliss, shown as it shipped and never touched; the chrome around it is the coded desktop's
([Motion](https://claudia.gallery/wiki/motion/#a-desktop-recreated-in-code)). Midjourney made what is on the screens: the wallpapers the picker
previews, the pictures in the windows, the worlds her takes start in, the drop's 3D backdrop and the objects made into
meshes.

## Every prompt

The complete prompt records, batch by batch, with what became of each image:

- [ESCAPE VELOCITY: 188 prompts](https://claudia.gallery/record/escape-velocity/prompts-midjourney/)
- [CLODYSSEY: 161 prompts, and the director's 70 notes](https://claudia.gallery/record/clodyssey/prompts-midjourney/)
- [BLISS: 138 prompts, and the 38 Animate requests](https://claudia.gallery/record/bliss/prompts-midjourney/)
- [AIRPLANE MODE: 149 prompts, and the 34 Animate requests](https://claudia.gallery/record/airplane-mode/prompts-midjourney/)
- [DOWNFORCE: 20 prompts, and what each pick became](https://claudia.gallery/record/downforce/prompts-midjourney/)
- [DON'T LET ME SCROLL: 130 prompts, the feed's 54, and the Animate loops](https://claudia.gallery/record/dont-let-me-scroll/prompts-midjourney/)
- [WHITEPILL: the colony's worlds, its places with nobody in them, and her dress](https://claudia.gallery/record/whitepill/prompts-midjourney/)
- [THE CAKE IS NOT A LIE: the test against frames of Portal 2, the library of places, and storyboard v5's X and Y frames](https://claudia.gallery/record/the-cake-is-not-a-lie/prompts-midjourney/)
- [AERO: 113 prompts, the loops of its video model, and every GPT Image 2.5 instruction](https://claudia.gallery/record/aero/prompts-midjourney/)


---
From the Claudia wiki: https://claudia.gallery/wiki/midjourney/
