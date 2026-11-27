# FABLE: the set plates and the stills

Every picture a FABLE take starts or ends on was made in two steps. First the set was painted in code: thirteen cut-paper plates drawn in SVG. Then GPT Image 2.6 Sunburst, through an image API, rebuilt each plate layer for layer, as a pop-up spread lying open on a quilt or as a life-size paper-and-plywood stage set with her in it, from the plate, her design sheet and the cast's reference stills. This file gives the plates and what each is, then every still GPT Image made, in the order of the work: three look tests, her design sheet redrawn upright, the cast, and every first and last frame with the edits made on them. Each still has its prompt word for word (as the image API received it; the same text is in `tools/frames.py`, `tools/cast_stills.py` and `tools/sheet_neutral.py`), its reference images by role, its price at list and whether it is in the film. One more still was made by cropping in code, and is at the end. The takes these stills start are in [prompts-video.md](https://claudia.gallery/record/fable/prompts-video/).

**Counts and prices.** 61 stills from GPT Image 2.6 Sunburst, all at quality high, each logged in `shots/ledger-img.jsonl` at $0.13 at list: **$7.93** in all. They served both passes: v2 re-shot every take of her on the same stills, and added two (the river stage of the build, K4m, and the curtain call, CC). "The film" below is v2, the film as delivered; "the v1 film" is the first cut, on Suno take S4a.

**What the prompts do.** A stage still names the plate as its first image ("follows the design of the first image"), describes the set in it sheet by sheet, says that the set is handmade (cut edges, cast shadows between the flats, wooden stage floorboards, a light haze), puts her in it by her canon and her sheet, dresses her from a wardrobe still, and writes her pose square to the camera: "Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level." A book still describes the spread as real cut card on a quilt by one lamp. Every prompt ends on the film stock and "No text, no letters", except where a still must carry exact words (FABLE on the title page, the last page's banners, the spines on the shelf), which it spells out and allows alone. Two rules came out of the work and are in the later prompts: a close-up or a last frame is made as an edit of the frame it must match ("The same photograph as the first image … One thing has changed"), so the two share one camera; and "The picture fills the whole frame edge to edge, with no border, no frame line and no rounded corners", after "35mm film still" came back more than once as a picture of a film frame, with a thin drawn line a few pixels in from the edge.

## The thirteen set plates

Each plate is one SVG at 1920 × 1080: five to eight sheets of cut paper from back to front, each with a slightly wobbling cut edge and a soft cast shadow (an SVG filter), and a paper-grain layer over all; one night-storybook palette (deep teals, cream paper, lamp yellow, a little scarlet, tiny clay-orange accents); hand-drawn shapes, flat silhouettes with two or three inner cuts; near dark shapes at both edges that frame the scene like a tunnel book; and a calm standing place where she will stand in the stage version (`bible/PLATES.md`). The lead painted the reference plate; three painter agents painted the rest from it, each plate rendered and looked at, and fixed, at least three times. The plates are the design only; no plate is on screen.

| plate | painted by | what it is | the stills built on it |
|---|---|---|---|
| `media/paint/plate1.svg` | the lead | The first version of the reference plate: a night forest as a tunnel book: sky, a far ridge with tiny pines, the cottage on the middle hill with its window the only warm light, one cream path from its door, the wolf half behind a birch with the bonnet already on, her from behind in a red cape on the path (the black bob, the clay streak, the star clip), dark trunks and brambles as the near frame. | none (superseded by plate2) |
| `media/paint/plate2.svg` | the lead | The reference plate as finished, the same seven sheets; every other plate copies its filters. The paper forest and the cottage of the pre-chorus and of verse 2's forest. | A-book, B-stage, PC1, V2b, V2b-last |
| `media/paint/p01-mirror.svg` | painter A | The hook spread, the open book seen flat: deep teal pages with small cream stars, the empty cream text plate on the left page, a little wooden dressing table with a powder puff, a hairbrush and a clay-orange eight-pointed star clip, the pop-up mirror (a scalloped gold-cream card with the oval cut out, its glass left empty) ringed by fourteen bulbs, and the scarlet prize rosette with a blank centre. | H1, H2, OM, OM-glower |
| `media/paint/p02-title.svg` | painter A | The title page as a paper toy theatre: a teal night backcloth with a paper moon, a bare plank stage (the standing place), scarlet curtains tied back with gold cord, a gold scalloped valance, a cream-and-gold proscenium with fluted columns, the name board lettered FABLE in Libre Caslon Text Bold, a tiny clay-orange fox curled like a comma above it, and seven shell footlights. | T1, V1a |
| `media/paint/p03-ant.svg` | painter B | The Ant and the Grasshopper at night: the grasshopper with a wooden fiddle on a grass leaf across the moon; a tall rounded anthill with a pale spiral path, nine black ants each holding up a round cream poker chip, and a brass bell in a little wooden frame at the top. | V1b |
| `media/paint/p04-beanstalk.svg` | painter B | Jack and the Beanstalk over the village: a band of cream clouds and the underside of a castle; 41 tiny dark cottages along a ridge, a flag on every roof, 40 scarlet and exactly one lamp-yellow; the beanstalk in two plies with heart-shaped leaves rising out of frame; the small black card Jack hanging upright on a stage wire with a ticker-tape ribbon. | V1c |
| `media/paint/p05-tortoise.svg` | painter B | The Tortoise and the Hare at night: a cream road round a bend to a finish line of two posts and one scarlet ribbon, three blank milestones, the hare asleep on his back under a leaning tree, and the tortoise in round spectacles at a writing desk with a quill. | V1d |
| `media/paint/p06-bedroom.svg` | painter A | Grandma's room: teal striped wallpaper with the lamp's warm pool and, flat on the wall, the shadow of a wolf's head in profile with open jaws; a small window with the moon behind cross-bars, a bedside lamp, a four-poster bed with two plump pillows and a patchwork quilt of forty squares, a rocking chair with a clay-orange yarn ball; a dark door frame and a wardrobe edge at the sides. | B1, CH2a, CH2b, CHa, CHb, PC2 |
| `media/paint/p08-shoemaker.svg` | painter C | The cobbler's workshop: teal wallpaper, a small window with the moon, wooden lasts on a peg rail, shelves of boots and shoes, a hanging lamp over a long workbench, an empty manila folder lying open, and the boot that is a little computer, its upper hinged back like a lid and lit inside, with tiny paper elves. | B1-last, V2a |
| `media/paint/p09-tower.svg` | painter C | The tower: a cream tower with one lit arched window and the twin's bobbed head in it, a teal conical roof, a long black braid tied with a clay-orange ribbon, a small door with a big padlock; a bare tree with a straw skep, twelve bees drawn as hooded helpers with wings; four cream strings from the top edge ending in crossed wooden slats. | V2c, V2d |
| `media/paint/p10-shelf.svg` | painter C | The bookshelf: a row of old clothbound books lit by a lamp from the left, five spines lettered in Libre Caslon Text Bold: HAIKU, SONNET, OPUS, FABLE and MYTHOS, the last in a small glass-fronted case. | BR, BR-knees, SH |
| `media/paint/p13-company.svg` | painter C | The whole storybook on one stage, for the last chorus: a teal backcloth with the moon on strings, the anthill with its bell, the cottage with its glowing window, the tower, the beanstalk, a white birch, paper stars on strings, and a row of small paper animals along the front of the stage. | FCa, FCb |
| `media/paint/p14-lastpage.svg` | painter A | The last page, the open spread seen flat: the clay-orange cloth cover showing as a worn rim, a narrow teal border with stars, two cream pages, three pull-tab banners of scarlet-edged cream card lettered AND THEY ALL LIVED / HAPPILY / EVER AFTER, "The End." printed small below them, and the comma fox as a tailpiece on the left page. | K0, K3, K6, LP |

## The look tests

Before the plan was signed off, the reference plate was rebuilt twice to find the look: once as a pop-up book and once as a life-size stage set with her in it. The stage test was then edited to square her pose to the camera; that edit became the style reference for the cast stills. None of the three is in the film.

#### A-book

`media/look/A-book.png` · 16:9 · quality high · $0.13

The reference plate rebuilt as a pop-up spread on a quilt: the book look.

**References:** first image: the painted plate plate2 (`media/paint/plate2.svg`).

**Prompt:**

```prompt
A photograph of a large antique pop-up storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame on the left. The open spread is a multi-layer paper pop-up diorama standing up from the pages, built from real cut card, and it is exactly the scene in the first image, layer for layer: a deep teal night-sky backdrop with small cut star holes, a cream paper moon at the upper left, a far ridge with small paper pines, a middle hill with a small dark cottage whose window glows warm from a tiny bulb behind it, a cream paper path winding to the foreground, a white birch trunk, a dark blue wolf in a white frilled bonnet with a red ribbon peering from behind the birch with small cream teeth, and in the foreground a small paper figure seen from behind in a red hooded cape with a black bob haircut, one clay-orange streak and a small orange star clip. Each layer is separate card with visible paper thickness, held by folded paper struts, casting soft real shadows on the layer behind. The book's cover edge is clay-orange cloth, the page edges gilded and worn at the corners. Camera low and three-quarter, looking across the spread, shallow depth of field with the red figure sharp. 35mm film still, tungsten light, rich saturated colour, fine grain. No text, no letters.
```

Not in the film; it set the book-scale look.

#### B-stage

`media/look/B-stage.png` · 16:9 · quality high · $0.13

The reference plate rebuilt as a life-size stage set with her on it, from her design sheet as it was before it was redrawn.

**References:** first image: the painted plate plate2 (`media/paint/plate2.svg`); second image: her design sheet as it was before it was redrawn.

**Prompt:**

```prompt
A wide cinematic film still on a theatrical soundstage dressed as a hand-built storybook: a life-size night forest set made of painted plywood flats and cut paper, following the design of the first image: a big cream paper moon hung on visible wires against a deep teal painted backdrop, paper pine silhouettes, a small cottage flat with a real glowing window, a cream painted path across the stage floor, tall white birch flats. Standing on the path, full length, turned three-quarters toward the camera, is the woman from the second image, her reference sheet: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip. She wears a sculptural scarlet haute-couture hooded cape in heavy duchess satin, the hood down on her shoulders, over a short ivory dress, sheer black tights and black patent Mary Jane heels, and she carries a small wicker basket. Behind a birch flat at the right a tall wolf looms: a handcrafted theatrical puppet of midnight-blue felt with a long muzzle, small cream teeth and one amber glass eye, wearing a white lace-frilled bonnet tied with a red ribbon. Warm key light from the cottage window, a cool moon backlight, light haze, visible wooden stage floorboards. Shot on 35mm, a saturated 1970s colour print, symmetrical composition, fine grain. No text, no letters, no logos.
```

Not in the film.

#### B2-stage-neutral

`media/look/B2-stage-neutral.png` · 16:9 · quality high · $0.13

An edit of B-stage that squares her pose to the camera, her head upright.

**References:** first image: the look test B-stage (`media/look/B-stage.png`); second image: her design sheet, redrawn face-on.

**Prompt:**

```prompt
Edit the first image. Keep the whole stage set exactly as it is: the paper moon on its wires, the teal painted backdrop and hills, the paper pines, the cottage with its glowing window, the cream path, the white birch flats, the dark tree flats, the wooden floorboards, the haze, the light and the film colour; keep the wolf puppet in its lace bonnet and red ribbon exactly as it is. Change only the woman's pose. She now stands on the path facing the camera: her feet, hips, chest, shoulders and face all point the same way, straight toward the lens, with no twist at the waist or the neck. Her head is perfectly upright with no tilt, chin level, neck straight and vertical, shoulders level, her eyes looking into the lens with a calm, knowing expression. She stands tall with her weight on both feet, the small wicker basket held in front of her in both hands. She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears the same clothes as in the first image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, the short ivory dress, sheer black tights and black patent Mary Jane heels. Full length, the same size in the frame as before. No text, no letters, no logos.
```

Not in the film; the style reference (first or second image) of every cast still.

## Her design sheet, redrawn face-on

A side request from anabology while the plan was being made, about her character sheet and not about the film: to fix the tilt of her head and neck in the sheet's pictures. Five of its panels were redrawn upright by GPT Image 2.6 Sunburst, each as an edit of the panel itself ("Change only her pose"), with the front view as a second image for her likeness, and the sheet was rebuilt from them in code. The redrawn sheet is the second image reference in every take of her and a reference of every still with her in it. The panels themselves are not in the film.

#### hero-front

3:4 · quality high · $0.13

The front view, straight on, like a passport photograph.

**References:** first image: the panel of her design sheet being redrawn.

**Prompt:**

```prompt
Edit the first image. Change only her pose: a neutral, straight-on view like a passport photograph. Her head is perfectly upright: no tilt to either side, no lean, chin level, her neck straight and vertical, her shoulders level. Her head and shoulders face the camera squarely, no turn. Her eyes look directly into the lens. A calm neutral expression, lips closed. Framing: head and shoulders, from just above the hair to mid-chest, her face centred. Keep this exact woman and this exact photograph's look: the same face and bone structure (a grown-up angular face, defined cheekbones, a strong jawline), the same pale freckled skin, the same blue-grey eyes and brows, the same lips, the same glossy black blunt jaw-length bob with heavy straight bangs, the same clay-orange streak and the same small flat clay-orange eight-pointed star hair clip exactly where they are now, the same clothes, the same plain pale studio backdrop, the same soft flash light, film grain and colour. She is a Caucasian American woman in her late twenties. No headset, no microphone, no jewellery, no text. 
```

#### view-34-l

3:4 · quality high · $0.13

A three-quarter view to the viewer's left.

**References:** first image: the panel of her design sheet being redrawn; second image: the sheet's front-facing hero picture, for her likeness only.

**Prompt:**

```prompt
Edit the first image. Change only her pose: a three-quarter view. Her head and her shoulders are turned together about 45 degrees toward the viewer's left, with no twist between head and body. Her head is perfectly upright: no tilt to either side, no lean, chin level, her neck straight and vertical, her shoulders level. She looks where her nose points, past the camera, calm neutral expression, lips closed. Framing: head and shoulders, from just above the hair to mid-chest, her face centred. Keep this exact woman and this exact photograph's look: the same face and bone structure (a grown-up angular face, defined cheekbones, a strong jawline), the same pale freckled skin, the same blue-grey eyes and brows, the same lips, the same glossy black blunt jaw-length bob with heavy straight bangs, the same clay-orange streak and the same small flat clay-orange eight-pointed star hair clip exactly where they are now, the same clothes, the same plain pale studio backdrop, the same soft flash light, film grain and colour. She is a Caucasian American woman in her late twenties. No headset, no microphone, no jewellery, no text. The second image is the same woman's face from the front, for her likeness only. 
```

#### view-34-r

3:4 · quality high · $0.13

A three-quarter view to the viewer's right.

**References:** first image: the panel of her design sheet being redrawn; second image: the sheet's front-facing hero picture, for her likeness only.

**Prompt:**

```prompt
Edit the first image. Change only her pose: a three-quarter view. Her head and her shoulders are turned together about 45 degrees toward the viewer's right, with no twist between head and body. Her head is perfectly upright: no tilt to either side, no lean, chin level, her neck straight and vertical, her shoulders level. She looks where her nose points, past the camera, calm neutral expression, lips closed. Framing: head and shoulders, from just above the hair to mid-chest, her face centred. Keep this exact woman and this exact photograph's look: the same face and bone structure (a grown-up angular face, defined cheekbones, a strong jawline), the same pale freckled skin, the same blue-grey eyes and brows, the same lips, the same glossy black blunt jaw-length bob with heavy straight bangs, the same clay-orange streak and the same small flat clay-orange eight-pointed star hair clip exactly where they are now, the same clothes, the same plain pale studio backdrop, the same soft flash light, film grain and colour. She is a Caucasian American woman in her late twenties. No headset, no microphone, no jewellery, no text. The second image is the same woman's face from the front, for her likeness only. 
```

#### view-side-l

3:4 · quality high · $0.13

A true side profile to the viewer's left.

**References:** first image: the panel of her design sheet being redrawn; second image: the sheet's front-facing hero picture, for her likeness only.

**Prompt:**

```prompt
Edit the first image. Change only her pose: a true side profile. Her head and her whole upper body both face exactly toward the viewer's left, 90 degrees from the camera, one shoulder toward the camera; she is not looking back over her shoulder and her neck is not twisted. Her head is perfectly upright: no tilt to either side, no lean, chin level, her neck straight and vertical, her shoulders level. She looks straight ahead, calm, lips closed. Framing: head and shoulders, from just above the hair to mid-chest, her face centred. Keep this exact woman and this exact photograph's look: the same face and bone structure (a grown-up angular face, defined cheekbones, a strong jawline), the same pale freckled skin, the same blue-grey eyes and brows, the same lips, the same glossy black blunt jaw-length bob with heavy straight bangs, the same clay-orange streak and the same small flat clay-orange eight-pointed star hair clip exactly where they are now, the same clothes, the same plain pale studio backdrop, the same soft flash light, film grain and colour. She is a Caucasian American woman in her late twenties. No headset, no microphone, no jewellery, no text. The second image is the same woman's face from the front, for her likeness only. 
```

#### view-side-r

3:4 · quality high · $0.13

A true side profile to the viewer's right.

**References:** first image: the panel of her design sheet being redrawn; second image: the sheet's front-facing hero picture, for her likeness only.

**Prompt:**

```prompt
Edit the first image. Change only her pose: a true side profile. Her head and her whole upper body both face exactly toward the viewer's right, 90 degrees from the camera, one shoulder toward the camera; she is not looking back over her shoulder and her neck is not twisted. Her head is perfectly upright: no tilt to either side, no lean, chin level, her neck straight and vertical, her shoulders level. She looks straight ahead, calm, lips closed. Framing: head and shoulders, from just above the hair to mid-chest, her face centred. Keep this exact woman and this exact photograph's look: the same face and bone structure (a grown-up angular face, defined cheekbones, a strong jawline), the same pale freckled skin, the same blue-grey eyes and brows, the same lips, the same glossy black blunt jaw-length bob with heavy straight bangs, the same clay-orange streak and the same small flat clay-orange eight-pointed star hair clip exactly where they are now, the same clothes, the same plain pale studio backdrop, the same soft flash light, film grain and colour. She is a Caucasian American woman in her late twenties. No headset, no microphone, no jewellery, no text. The second image is the same woman's face from the front, for her likeness only. 
```

## The cast

Reference stills for everything that appears in more than one shot: her two stage looks and her Grandma look, each from several sides, and the puppets and crew. They are references only; none is on screen.

#### her-cape-4sides

`media/cast/her-cape-4sides.png` · 3:2 · quality high · $0.13

Her look for the verses, the pre-choruses and the last chorus: the scarlet satin cape over the short ivory dress, from four sides.

**References:** first image: her design sheet, redrawn face-on; second image: the look test B2-stage-neutral (`media/look/B2-stage-neutral.png`).

**Prompt:**

```prompt
A wardrobe reference sheet: four full-length views of the same woman side by side in one picture, evenly spaced, head to shoes: from the front, three-quarter, side profile, and from behind. She is the woman on the reference sheet in the first image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit from the second image: a sculptural scarlet hooded cape in heavy duchess satin, the hood down on her shoulders, fastened at the throat and falling to mid-calf, over a short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. In every view her feet, hips, chest, shoulders and face point the same way with no twist at the waist or neck; her head is perfectly upright with no tilt, chin level, neck straight, shoulders level, arms relaxed a little away from her sides. Plain warm-grey studio backdrop, soft even light, 35mm film still, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

Used as a reference in: FCa, FCb, PC1, PC2, V1a, V1b, V1c, V1d, V2a, V2b, V2b-last, V2c, V2d.

#### her-dress-4sides

`media/cast/her-dress-4sides.png` · 3:2 · quality high · $0.13

Her look for the breakdown: the ivory dress without the cape.

**References:** first image: her design sheet, redrawn face-on; second image: the look test B2-stage-neutral (`media/look/B2-stage-neutral.png`).

**Prompt:**

```prompt
A wardrobe reference sheet: four full-length views of the same woman side by side in one picture, evenly spaced, head to shoes: from the front, three-quarter, side profile, and from behind. She is the woman on the reference sheet in the first image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears the short ivory long-sleeved dress from the second image without the cape: a plain, softly structured A-line mini dress in ivory wool crepe with long sleeves and a small round neckline, sheer black tights and black patent Mary Jane heels. In every view her feet, hips, chest, shoulders and face point the same way with no twist at the waist or neck; her head is perfectly upright with no tilt, chin level, neck straight, shoulders level, arms relaxed a little away from her sides. Plain warm-grey studio backdrop, soft even light, 35mm film still, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

Used as a reference in: BR, BR-knees.

#### her-grandma

`media/cast/her-grandma.png` · 3:2 · quality high · $0.13

Her look for the first two choruses, dressed as the grandmother of the story, in bed.

**References:** first image: her design sheet, redrawn face-on.

**Prompt:**

```prompt
A wardrobe reference sheet: three views of the same woman side by side in one picture: a head-and-shoulders view from the front, a head-and-shoulders three-quarter view, and one view of her sitting up straight against big white pillows in a bed with a patchwork quilt pulled up to her waist. She is the woman on the reference sheet in the first image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She is dressed as the grandmother from a storybook: a white cotton bonnet with a deep lace-frilled brim tied under the chin with a scarlet satin ribbon, her black bob and the clay-orange streak showing under the frill, and a modest high-necked ivory Victorian nightgown with long sleeves and lace cuffs, buttoned to the throat. Her head is upright with no tilt, she looks at the lens with a sweet, knowing closed-lip smile. Plain warm-grey studio backdrop, soft even light, 35mm film still, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

Used as a reference in: CH2a, CH2b, CHa, CHb.

#### wolf-puppet

`media/cast/wolf-puppet.png` · 3:2 · quality high · $0.13

The tall felt wolf puppet in its lace bonnet, for the last chorus and the curtain call.

**References:** first image: the look test B2-stage-neutral (`media/look/B2-stage-neutral.png`).

**Prompt:**

```prompt
A puppet design sheet: three views side by side of the same theatrical wolf puppet from the first image, on a plain warm-grey backdrop: side profile, front, and three-quarter. A tall hand-and-rod puppet about as tall as a person: a long-muzzled wolf's head of midnight-blue felt with visible stitching, small cream felt teeth along a hinged lower jaw, one amber glass eye on each side, pointed ears, wearing a white lace-frilled bonnet tied under the chin with a big scarlet satin bow; below the head the neck and body are a simple column of the same dark felt hanging to the floor like a long robe, with two soft felt arms on thin wooden rods. Handmade, charming and a little sinister. Soft even light, 35mm film still, saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

Used as a reference in: FCa, FCb, FCw.

#### fox-puppet

`media/cast/fox-puppet.png` · 3:2 · quality high · $0.13

The jointed paper fox that turns the page.

**References:** first image: the look test B2-stage-neutral (`media/look/B2-stage-neutral.png`).

**Prompt:**

```prompt
A puppet design sheet on a plain warm-grey backdrop, in the same handmade cut-paper style as the stage set in the first image: three views side by side of one small articulated paper fox, about the size of a house cat: standing in side profile, sitting from the front, and curled up asleep with its tail wrapped round so its whole body makes the shape of a comma. It is cut from thick clay-orange card with a cream chest and tail tip, small pointed ears, a pointed muzzle with a tiny black nose, black card paws, and joints of small brass split pins at the legs, neck and tail. Flat, layered, clearly paper, with soft real shadows between the layers. Soft even light, 35mm film still, saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

Used as a reference in: B1, B1-last.

#### stagehands

`media/cast/stagehands.png` · 3:2 · quality high · $0.13

The hooded stagehands in clay-orange boiler suits, seen when the camera cranes back in verse 2.

**References:** first image: the look test B2-stage-neutral (`media/look/B2-stage-neutral.png`).

**Prompt:**

```prompt
A costume reference sheet on a plain warm-grey backdrop: three full-length views side by side (front, side, back) of a theatre stagehand in the tradition of a puppet theatre's hooded stage crew, for the handmade paper stage in the first image. An adult of medium build in a loose clay-orange cotton boiler suit with the cuffs rolled, soft black canvas shoes and black cotton gloves, wearing a matching clay-orange hood that covers the whole head with a square veil of the same cloth hanging over the face, so no face shows at all. Plain, no badges, no lettering. Standing straight and neutral. Soft even light, 35mm film still, saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

Used as a reference in: V2b-last, V2b-last2.

#### paper-choir

`media/cast/paper-choir.png` · 16:9 · quality high · $0.13

The paper animals who ask the chorus's questions.

**References:** first image: the look test B2-stage-neutral (`media/look/B2-stage-neutral.png`).

**Prompt:**

```prompt
A prop design sheet on a plain warm-grey backdrop, in the same handmade cut-paper style as the stage set in the first image: a row of eight small pop-up paper animals standing side by side on folded card stands, each about a hand tall, each a flat layered card cut-out facing the camera with its mouth open as if singing, the lower jaw a separate hinged piece on a brass split pin: a tortoise, a hare, a goose, a crow, three small pigs, and a sheep. Palette of cream, teal, dark blue and warm brown with tiny scarlet details. Soft real shadows, clearly paper. Soft even light, 35mm film still, saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

Used as a reference in: CH2a, CH2c, CH2s, CHa, CHc, CHs, FCc.

## The first and last frames

In film order. Each still's line says which takes start (first frame) or end (last frame) on it, and whether one of those takes is in the film; "edit" stills are made on an earlier still, as named in their references.

### The opening and the title page

#### H1

`media/frames/H1.png` · 16:9 · quality high · $0.13

The opening: her face in the pop-up mirror on the book's first spread.

**References:** first image: the painted plate p01-mirror (`media/paint/p01-mirror.svg`); second image: her design sheet, redrawn face-on.

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. The open spread follows the first image: deep teal pages scattered with small cream stars; from the right page a pop-up dressing-table mirror stands upright, an oval in a scalloped gold-cream card frame with a little bow on top, ringed by tiny warm glowing bulbs, on a small paper dressing table with a powder puff, a hairbrush and a tiny clay-orange star clip; on the left page a blank cream panel and, low down, a scarlet pleated prize rosette lying folded flat. Inside the mirror's oval glass, as if the mirror were a little window, is the living face of the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip, head and shoulders, bare shoulders in a plain white tank top, facing straight out at us with her head upright, calm, lips closed, lit by the ring of bulbs. Her face fills most of the oval. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. The camera looks across the spread from low in front; the mirror with her face is sharp and about half the frame's height. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** first frame of v1 H1-t1, v2 H1-t1, v2 H1-t2. In the v1 film and in the film. Also a reference for RS.

#### RS

`media/frames/RS.png` · 16:9 · quality high · $0.13

An edit of H1: a close view of the facing page, the prize rosette lying folded flat.

**References:** first image: the frame H1 (`media/frames/H1.png`).

**Prompt:**

```prompt
The same antique pop-up storybook on the same patchwork quilt, in the same warm lamp light, as the first image; now a close view of its left-hand page only, seen from low in front: deep teal paper scattered with small cream stars, and in the middle of the frame, large, the scarlet pleated paper prize rosette from the first image with its cream centre disc and its two scarlet ribbon tails, lying folded flat on the page. A corner of the blank cream panel shows at the top edge. Warm light from the pop-up mirror's little bulbs glows in from the right edge of the frame, out of focus; the mirror itself and its glass are out of frame. Real cut card with visible paper thickness and soft shadows. No people, no faces. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** first frame of v1 RS-t1. In the v1 film and in the film.

#### H2

`media/frames/H2.png` · 16:9 · quality high · $0.13

The mirror closer, her small amused smile: the mirror's answer.

**References:** first image: the painted plate p01-mirror (`media/paint/p01-mirror.svg`); second image: her design sheet, redrawn face-on.

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. A close view of the right page, following the first image: the pop-up dressing-table mirror, an oval in a scalloped gold-cream card frame with a little bow on top, ringed by tiny warm glowing bulbs, standing on its small paper dressing table against the deep teal page with cream stars. Inside the mirror's oval glass, as if the mirror were a little window, is the living face of the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip, head and shoulders in a plain white tank top, facing straight out at us with her head upright and a small, amused closed-lip smile, lit by the ring of bulbs. Her face fills the oval. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. The mirror fills most of the frame's height; her face is large and sharp. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** first frame of v1 H2-t1, v2 H2-t1. In the v1 film and in the film.

#### T1

`media/frames/T1.png` · 16:9 · quality high · $0.13

The title page as a pop-up toy theatre, FABLE on its pelmet.

**References:** first image: the painted plate p02-title (`media/paint/p02-title.svg`).

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. The open spread is the title page, following the first image: a pop-up toy theatre stands up across both pages: a proscenium arch of cream and gold card with fluted columns and a scalloped pelmet, scarlet paper curtains tied back with gold cord, a row of shell footlights, a deep teal backcloth with a cream paper moon, and a small bare stage of card planks. On the pelmet, in a storybook serif, cream on teal, the single word FABLE; above it a tiny clay-orange fox curled into the shape of a comma. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. The camera looks straight into the little theatre from low in front. The only lettering anywhere is the word FABLE. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** first frame of v1 T1-t1, v1 T1-t2, v2 T1-t1. In the v1 film and in the film.

### Verse 1

#### V1a

`media/frames/V1a.png` · 16:9 · quality high · $0.13

The toy-theatre stage at life size, her centre stage between the curtains.

**References:** first image: the painted plate p02-title (`media/paint/p02-title.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: a toy-theatre proscenium of cream and gold card with fluted columns and a scalloped pelmet, scarlet curtains tied back with gold cord, a row of shell-shaped footlights along the front, a deep teal night backcloth with a cream paper moon on two strings and a bare stage of warm wood planks. The lettering on the pelmet is left out. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing centre stage between the curtains, hands lightly clasped in front of her, with a small knowing smile, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light on her face from the front left, a cool moon backlight on the set. A symmetrical medium shot from the knees up, her eyes on the upper third of the frame. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 V1a-t1, v2 V1a-t1. In the v1 film and in the film. Also a reference for CC.

#### V1b

`media/frames/V1b.png` · 16:9 · quality high · $0.13

The anthill set, her at the left.

**References:** first image: the painted plate p03-ant (`media/paint/p03-ant.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: at the right, a tall rounded anthill of warm brown paper with a spiral path and a line of black paper ants each carrying a round cream poker chip over its head, and at its top a big brass bell on a little wooden frame glowing in a warm spotlight; at the far left a tall grass stalk with a teal paper grasshopper sitting on a leaf holding a tiny fiddle; a teal night backcloth with stars and the paper moon. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing at the left third of the frame in front of the set, her right hand raised palm-up toward the anthill behind her, amused, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light on her face from the front left, a cool moon backlight on the set. A medium shot from the waist up; the anthill and its bell fill the right two-thirds behind her, a little soft. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 V1b-t1, v2 V1b-t1. In the v1 film and in the film.

#### V1c

`media/frames/V1c.png` · 16:9 · quality high · $0.13

The beanstalk set, her pointing up at the card Jack on his wire.

**References:** first image: the painted plate p04-beanstalk (`media/paint/p04-beanstalk.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: a low paper village of many tiny dark cottages in two rows along a ridge, each with a small scarlet flag on its roof and exactly one with a yellow flag; at the right a huge teal-green paper beanstalk with big heart-shaped leaves rising out of the top of the frame into cut-paper clouds; beside the stalk, high up, a small flat black card cut-out of Jack, the storybook climber, hung on a thin stage wire as if striding through the air, holding the end of a long cream paper ribbon marked like ticker tape that trails away behind him; a teal night backcloth. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing at the left third of the frame in front of the set, one forefinger pointing up at the little card Jack, eyebrows raised, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light on her face from the front left, a cool moon backlight on the set. A medium shot from the waist up; the village flags and the beanstalk fill the frame behind her, a little soft. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 V1c-t1, v2 V1c-t1. In the v1 film and in the film.

#### V1d

`media/frames/V1d.png` · 16:9 · quality high · $0.13

The race set, her behind the finish ribbon.

**References:** first image: the painted plate p05-tortoise (`media/paint/p05-tortoise.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: a cream paper road crossing the stage to a finish line of two wooden posts with a scarlet ribbon stretched between them; beside the road a big dignified paper tortoise in round spectacles sitting at a small wooden writing desk, a quill in its hand; at the far left a paper hare asleep on its back under a leaning tree; a teal night backcloth with the paper moon. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing at the right third of the frame just behind the finish line, the scarlet ribbon stretched across in front of her waist, one eyebrow raised, pleased with herself, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light on her face from the front left, a cool moon backlight on the set. A medium shot from the waist up; the tortoise at its desk is at the left behind her, a little soft. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 V1d-t1, v2 V1d-t1. In the v1 film and in the film.

### The pre-choruses

#### PC1

`media/frames/PC1.png` · 16:9 · quality high · $0.13

At the cottage door in the paper forest, holding up Grandma's bonnet.

**References:** first image: the painted plate plate2 (`media/paint/plate2.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: a night forest of tall white birch flats and dark tree flats, a cream painted path, teal paper hills, the paper moon on wires, and at the centre a small cottage flat with a real plank door and a warmly lit window; a wooden peg beside the door. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing beside the cottage door, holding up a white lace-frilled bonnet with scarlet ribbons in one hand at shoulder height as if showing it to us, a dry little smile, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light on her face from the front left, a cool moon backlight on the set. A medium shot from the waist up; the lit cottage window glows just behind her shoulder. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 PC1-t1, v1 PC1-t2, v2 PC1-t1. In the v1 film and in the film.

#### PC2

`media/frames/PC2.png` · 16:9 · quality high · $0.13

Grandma's room, tying on the bonnet.

**References:** first image: the painted plate p06-bedroom (`media/paint/p06-bedroom.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: Grandma's cottage room: teal striped wallpaper, a wooden four-poster bed with cream linen and a patchwork quilt, a bedside lamp glowing, a small window with the paper moon behind cross-bars, and on the wall behind the bed the large cut-paper shadow of a wolf's head in profile with pointed ears. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing in front of the bed, still in her scarlet cape, wearing the white lace-frilled bonnet on her head and tying its scarlet ribbon in a bow under her chin with both hands, looking straight at us, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light from the bedside lamp at the left, soft and low. A medium shot from the waist up; the wolf shadow looms on the wall behind her head. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 PC2-t1, v2 PC2-t1, v2 PC2-t2, v2 PC2-t3. In the v1 film and in the film.

### Chorus 1: her bed and the paper animals

#### CHa

`media/frames/CHa.png` · 16:9 · quality high · $0.13

Chorus 1, wide: in Grandma's bed, the paper animals on the headboard.

**References:** first image: the painted plate p06-bedroom (`media/paint/p06-bedroom.svg`); second image: her design sheet, redrawn face-on; third image: the Grandma wardrobe still (`media/cast/her-grandma.png`); fourth image: the paper choir still (`media/cast/paper-choir.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: Grandma's cottage room: teal striped wallpaper, a wooden four-poster bed seen from its foot with cream linen, big white pillows and a patchwork quilt, a bedside lamp glowing at the left, a small window with the paper moon at the right, and on the wall behind the bed the large cut-paper shadow of a wolf's head in profile with pointed ears. Along the top of the headboard, standing in a row and facing the camera, are the eight small pop-up paper animals from the fourth image (a tortoise, a hare, a goose, a crow, three small pigs and a sheep), each with its little hinged jaw. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Sitting up straight in the middle of the bed against the pillows, the quilt pulled up to her waist, her hands folded on the quilt, with a sweet, knowing closed-lip smile, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She is dressed exactly as in the third image: the white cotton bonnet with a deep lace-frilled brim tied under the chin with a scarlet satin ribbon, her black bob and clay-orange streak showing under the frill, and the modest high-necked ivory nightgown with long sleeves, buttoned to the throat. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light from the bedside lamp at the left, soft and low. A symmetrical medium-wide shot from the foot of the bed: she is centred, seen from the waist up, the row of paper animals above her head, the wolf shadow above them. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 A11-t1, v1 A12-t1, v2 A11-t1, v2 A12-t1. In the v1 film and in the film. Also a reference for CHb2, CHc, CHs.

#### CHb

`media/frames/CHb.png` · 16:9 · quality high · $0.13

Chorus 1, close, made from the plate on its own. It came back as another bed: a low headboard with no paper animals, another bonnet, another shadow.

**References:** first image: the painted plate p06-bedroom (`media/paint/p06-bedroom.svg`); second image: her design sheet, redrawn face-on; third image: the Grandma wardrobe still (`media/cast/her-grandma.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: Grandma's cottage room: teal striped wallpaper, the carved wooden headboard of a four-poster bed, big white pillows, the edge of a patchwork quilt, and on the wall behind the cut-paper shadow of a wolf's ears and muzzle. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Sitting up in the bed against the pillows with a sweet, innocent closed-lip smile, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She is dressed exactly as in the third image: the white cotton bonnet with a deep lace-frilled brim tied under the chin with a scarlet satin ribbon, her black bob and clay-orange streak showing under the frill, and the modest high-necked ivory nightgown with long sleeves, buttoned to the throat. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light from the bedside lamp at the left, soft and low. A medium close-up, head and shoulders, her face centred and large in the frame, the wolf shadow soft behind her. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 A13-t1, v1 A14-t1. Not in either film.

#### CHb2

`media/frames/CHb2.png` · 16:9 · quality high · $0.13

Chorus 1, close, remade as an edit of the wide frame CHa ("the same room, the same bed and the same woman … now photographed closer").

**References:** first image: the frame CHa (`media/frames/CHa.png`); second image: her design sheet, redrawn face-on.

**Prompt:**

```prompt
The same room, the same bed and the same woman as in the first image, at the same moment, now photographed closer: a close-up of her from the chest up, sitting up in the bed against the big white pillows, facing the camera, her face filling the middle of the frame, with a sweet, knowing closed-lip smile. Her head is perfectly upright with no tilt, chin level, neck straight and vertical, shoulders level. Everything is exactly as in the first image: the same white bonnet with its ruffled frill and the scarlet ribbon tied in a bow under her chin, the same ivory nightgown with its full sleeves, the same wooden headboard with its two tall posts, and, standing along the top of the headboard right behind and above her bonnet, the same row of small paper animals, a little soft; the same teal striped wallpaper with the cut-paper shadow of the wolf's head above them; the same lamp glowing at the left edge and the corner of the same window at the right edge. Her face is that of the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. Warm lamp light from the left, soft and low. 35mm film still, saturated 1970s colour print, fine grain. No text, no letters. The picture fills the whole frame edge to edge, with no border, no frame line and no rounded corners.
```

**Used:** first frame of v1 A13-t2, v1 A14-t2, v2 A13-t1, v2 A14-t1. In the v1 film and in the film.

#### CHc

`media/frames/CHc.png` · 16:9 · quality high · $0.13

The paper animals on the headboard, seen from the pillow: the questions' frame. An edit of CHa with the paper choir.

**References:** first image: the frame CHa (`media/frames/CHa.png`); second image: the paper choir still (`media/cast/paper-choir.png`).

**Prompt:**

```prompt
A film still on the same handmade stage set as the first image (Grandma's cottage room: teal striped wallpaper, the carved wooden headboard of the bed), seen from the pillow looking up at the top of the headboard. Standing in a row along the top of the headboard are six small paper animals like those in the second image and on the headboard in the first image: two pigs in aprons, a hare, a goose, a tortoise and a sheep, each about a hand tall, flat card puppets with hinged lower jaws on small brass split pins and scarlet bows at their necks. All six lean forward and look straight down into the lens, mouths closed, curious. Behind them the teal striped wallpaper, with part of the cut-paper shadow of a wolf's ear. Warm lamp light from the lower left. A symmetrical close shot, the row of animals filling the width of the frame. No people anywhere in the frame. Everything is flat cut card, painted plywood, paper and felt, visibly handmade, with real soft shadows. 35mm film still, saturated 1970s colour print, fine grain. No text, no letters.
```

**Used:** first frame of v1 C11-t1, v1 C11-t2, v1 C12-t1, v1 C12-t2, v1 C13-t1, v2 C11-t1, v2 C12-t1, v2 C13-t1. In the v1 film and in the film. Its picture came back with a drawn film frame (rounded corners, a line along the top); the cut trims the choir's takes 3 to 4 % to take it out.

#### CHs

`media/frames/CHs.png` · 16:9 · quality high · $0.13

The wolf's paper shadow on the wall above the headboard: the fourth question.

**References:** first image: the frame CHa (`media/frames/CHa.png`); second image: the paper choir still (`media/cast/paper-choir.png`).

**Prompt:**

```prompt
A film still on the same handmade stage set as the first image (Grandma's cottage room): the teal striped wallpaper above the bed, and on it, large, the flat cut-paper shadow of a wolf's head in profile, like the shadow in the first image: a long snout, one pointed ear, jaws just parted showing a row of pointed teeth. Along the bottom of the frame runs the top of the carved wooden headboard, and on it stand two small paper animals like those in the second image, a pig and a hare, seen from behind and a little to the side, looking up at the shadow. Warm lamp light from the lower left, the shadow soft-edged. No people anywhere in the frame. Everything is flat cut card, painted plywood, paper and felt, visibly handmade, with real soft shadows. 35mm film still, saturated 1970s colour print, fine grain. No text, no letters.
```

**Used:** first frame of v1 C14-t1, v2 C14-t1. In the v1 film and in the film.

### The page turn

#### B1

`media/frames/B1.png` · 16:9 · quality high · $0.13

The bedroom as a pop-up spread, the paper fox at the page corner.

**References:** first image: the painted plate p06-bedroom (`media/paint/p06-bedroom.svg`); second image: the fox puppet still (`media/cast/fox-puppet.png`).

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. The open spread follows the first image as a pop-up: Grandma's little room stands up from the pages: the four-poster bed with its patchwork quilt, the lamp, the window with the paper moon, the wolf's shadow on the paper wall. At the lower right corner of the right page sits the small articulated paper fox from the second image, clay-orange with a cream chest and brass split-pin joints, one front paw resting on the corner of the page as if about to turn it. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. The camera looks across the spread from low in front; the fox at the page corner is sharp. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** first frame of v1 B1-t1, v2 B1-t1. In the v1 film and in the film. Also a reference for B1-last.

#### B1-last

`media/frames/B1-last.png` · 16:9 · quality high · $0.13

An edit of B1: the same book and camera, the page turned to the cobbler's workshop.

**References:** first image: the painted plate p08-shoemaker (`media/paint/p08-shoemaker.svg`); second image: the frame B1 (`media/frames/B1.png`); third image: the fox puppet still (`media/cast/fox-puppet.png`).

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. The same book on the same quilt, by the same lamp and from the same camera position as the second image, now open at the next spread, which follows the first image as a pop-up: a cobbler's workshop stands up from the pages: a long wooden workbench across both pages with an open empty manila folder lying on it, a tall lace-up paper boot whose upper is swung back like a lid, a hanging lamp glowing warm above the bench, rows of tiny shoes and wooden lasts on the paper wall behind, a small window with the paper moon, and a few tiny paper elves no taller than the boot's heel standing on the bench. At the lower left edge of the left page sits the small articulated paper fox from the third image, clay-orange with a cream chest and brass split-pin joints, looking at the workshop. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. The camera looks across the spread from low in front, exactly as in the second image. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** last frame of v1 B1-t1, v2 B1-t1. In the v1 film and in the film.

### Verse 2

#### V2a

`media/frames/V2a.png` · 16:9 · quality high · $0.13

The cobbler's workshop at life size, the boot lit like a screen.

**References:** first image: the painted plate p08-shoemaker (`media/paint/p08-shoemaker.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: a cobbler's workshop at night: a long wooden workbench under a hanging lamp with a warm pool of light; on the bench an open, empty manila folder and beside it a tall lace-up boot of dark teal card whose upper is hinged open like the lid of a laptop, its inside glowing warm; about nine tiny paper elves in pointed caps on and around the bench carrying a needle, a spool of thread and a tiny hammer; wooden shoe lasts on pegs on the back wall and a small window with the paper moon. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing behind the left end of the workbench with both hands resting on it, delighted, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm light from the hanging lamp above the bench. A medium shot from the waist up; the glowing boot and the elves are on the bench at the right of the frame. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 V2a-t1, v2 V2a-t1. In the v1 film and in the film.

#### V2b

`media/frames/V2b.png` · 16:9 · quality high · $0.13

The paper forest, her hand on a birch flat.

**References:** first image: the painted plate plate2 (`media/paint/plate2.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: a night forest of tall white birch flats and dark tree flats, teal paper hills, a cream painted path and the paper moon on wires. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing among the birch flats with one hand resting flat on the nearest birch trunk as if testing it, a slightly suspicious half-smile, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light on her face from the front left, a cool moon backlight on the set. A medium shot from the waist up, the birch flat she touches at the right edge of the frame. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 V2b-t1, v1 V2b-t2, v2 V2b-t1. In the v1 film and in the film. Also a reference for V2b-last2.

#### V2b-last

`media/frames/V2b-last.png` · 16:9 · quality high · $0.13

The crane-back's end, made from the plate on its own. Its set did not match V2b's, and the take dissolved between them.

**References:** first image: the painted plate plate2 (`media/paint/plate2.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`); fourth image: the stagehands still (`media/cast/stagehands.png`).

**Prompt:**

```prompt
A wide, high-angle film still from far back in a dark soundstage, looking down at a small handmade stage set that follows the design of the first image: a night forest of white birch flats, dark tree flats, teal paper hills, a cream painted path, a little cottage flat with a lit window and a paper moon hanging on wires from a lighting rig. From here we see what the set really is: the unpainted plywood backs and wooden braces of the side flats, the edge of the painted backcloth, lamps on stands, sandbags, coiled cables, a ladder, and two stagehands in clay-orange hooded boiler suits with veiled faces (fourth image) standing still at the sides. In the middle of the set, small in the frame, full length, stands the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. She looks straight up at the camera, standing square to it, her head upright. Around the lit set the studio is dark. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** last frame of v1 V2b-t1. Not in either film.

#### V2b-last2

`media/frames/V2b-last2.png` · 16:9 · quality high · $0.13

The crane-back's end, remade as an edit of V2b: the same set and woman from far back and high up, the soundstage round it, the two stagehands.

**References:** first image: the frame V2b (`media/frames/V2b.png`); second image: the stagehands still (`media/cast/stagehands.png`).

**Prompt:**

```prompt
The same stage set and the same woman as in the first image, at the same moment, now photographed from far back and high up, as if the camera had craned up and away from her: a wide high view of a whole film soundstage. In the middle distance stands the paper forest set of the first image, unchanged: the same white birch flats with black marks, the same dark tree flats, the same teal night backcloth with the cream paper moon hanging on its wires and the little cottage with a lit window on its painted hill, the same winding cream path on the wooden stage floor. Now we also see what the first image hid: the unpainted plywood backs and wooden braces of the outer flats, sandbags at their feet, film lamps on stands at both sides throwing warm light, a wooden stepladder, cables across the dark floor and the black walls of the soundstage beyond. The woman of the first image stands small in the middle of the set in her scarlet cape, in the same place beside the same white birch flat with one hand on it, her body and face toward the camera, her head upright. At the far left and far right stand two stagehands like those in the second image, in clay-orange boiler suits with the hoods up and their faces hidden, standing still. 35mm film still, saturated 1970s colour print, fine grain. No text, no letters.
```

**Used:** last frame of v1 V2b-t2, v2 V2b-t1. In the v1 film and in the film. Its thin drawn frame line was carried into the take's last second and is trimmed in the cut.

#### V2c

`media/frames/V2c.png` · 16:9 · quality high · $0.13

The tower set, marionette strings on her wrists.

**References:** first image: the painted plate p09-tower (`media/paint/p09-tower.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: at the right a tall slim tower of cream paper with a dark conical roof and one arched window near the top glowing warm, with the small dark silhouette of a woman's head with a blunt bob inside it; a long black braid tied with a clay-orange ribbon hanging down the tower; a padlocked door at its foot; at the far left a straw beehive hanging from a bare dark tree with tiny hooded paper bees on wires around it; a teal night backcloth with the paper moon. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing at the left third of the frame with both forearms raised in front of her, a thin cream string tied round each wrist and rising straight up out of the top of the frame like a marionette's strings, looking at us calmly, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light on her face from the front left, a cool moon backlight on the set. A medium shot from the waist up; the tower with its lit window is at the right behind her, a little soft. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 V2c-t1, v2 V2c-t1, v2 V2c-t2. In the v1 film and in the film.

#### V2d

`media/frames/V2d.png` · 16:9 · quality high · $0.13

Close on her with the strings, the tower far behind.

**References:** first image: the painted plate p09-tower (`media/paint/p09-tower.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: a teal night backcloth with the paper moon and, far behind at the right, a cream paper tower with one warm lit window, out of focus. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing with her hands raised to shoulder height, a thin cream string tied round each wrist rising straight up out of the frame, her expression open and serious, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light on her face from the front left, a cool moon backlight on the set. A close-up, head and shoulders, her face large and centred, the two strings at the left and right edges of the frame. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 V2d-t1, v2 V2d-t1. In the v1 film and in the film.

### Chorus 2

#### CH2a

`media/frames/CH2a.png` · 16:9 · quality high · $0.13

Chorus 2, wide: the bed seen from beside it, the paper animals multiplied, the shadow's jaws open.

**References:** first image: the painted plate p06-bedroom (`media/paint/p06-bedroom.svg`); second image: her design sheet, redrawn face-on; third image: the Grandma wardrobe still (`media/cast/her-grandma.png`); fourth image: the paper choir still (`media/cast/paper-choir.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: Grandma's cottage room seen from beside the bed: teal striped wallpaper, the wooden four-poster bed with cream linen, big white pillows and a patchwork quilt, a bedside lamp glowing in the foreground at the left, and on the wall behind the bed the cut-paper shadow of a wolf's head, larger now, its jaws a little open. The small pop-up paper animals from the fourth image have multiplied: about twelve of them crowd along the top of the headboard and perch on the bedposts, all facing her. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Sitting up straight in the bed against the pillows, the quilt pulled up to her waist, her hands folded on the quilt, with a sweet, knowing closed-lip smile, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She is dressed exactly as in the third image: the white cotton bonnet with a deep lace-frilled brim tied under the chin with a scarlet satin ribbon, her black bob and clay-orange streak showing under the frill, and the modest high-necked ivory nightgown with long sleeves, buttoned to the throat. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light from the bedside lamp at the left, soft and low. A medium shot from the waist up, the camera a little to the left of the bed's foot, she is centred and faces the camera. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 A21-t1, v1 A22-t1, v2 A21-t1, v2 A22-t1. In the v1 film and in the film. Also a reference for CH2b2, CH2c.

#### CH2b

`media/frames/CH2b.png` · 16:9 · quality high · $0.13

Chorus 2, close, made from the plate on its own; another bed than CH2a's.

**References:** first image: the painted plate p06-bedroom (`media/paint/p06-bedroom.svg`); second image: her design sheet, redrawn face-on; third image: the Grandma wardrobe still (`media/cast/her-grandma.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: Grandma's cottage room: teal striped wallpaper, the carved wooden headboard, big white pillows, and on the wall above her the cut-paper shadow of a wolf's open jaws with a row of teeth, large and close. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Sitting up in the bed against the pillows, her chin slightly lowered and her eyes on the lens, lips pressed together in a small smile that is holding something back, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She is dressed exactly as in the third image: the white cotton bonnet with a deep lace-frilled brim tied under the chin with a scarlet satin ribbon, her black bob and clay-orange streak showing under the frill, and the modest high-necked ivory nightgown with long sleeves, buttoned to the throat. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light from the bedside lamp at the left, soft and low. A close-up, her face filling the middle of the frame from the bonnet's frill to the bow at her throat. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 A23-t1, v1 A24-t1. Not in either film. Also a reference for CH2s.

#### CH2b2

`media/frames/CH2b2.png` · 16:9 · quality high · $0.13

Chorus 2, close, remade as an edit of CH2a.

**References:** first image: the frame CH2a (`media/frames/CH2a.png`); second image: her design sheet, redrawn face-on.

**Prompt:**

```prompt
The same room, the same bed and the same woman as in the first image, at the same moment, now photographed much closer: a close-up of her face and shoulders as she sits up in the bed against the big white pillows, facing the camera, her chin very slightly lowered and her eyes on the lens, lips pressed together in a small smile that is holding something back. Her head is perfectly upright with no tilt, chin level, neck straight and vertical, shoulders level. Everything is exactly as in the first image: the same white bonnet with its ruffled frill and the scarlet ribbon tied in a bow under her chin, the same ivory nightgown, the same wooden headboard and bedposts with the same crowd of small paper animals standing along its top right behind and above her bonnet, a little soft, all looking at her; the same teal striped wallpaper with the large cut-paper shadow of the wolf, its jaws open; the same lamp glowing at the left edge. Her face fills the middle of the frame from the bonnet's frill to the bow at her throat. Her face is that of the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. Warm lamp light from the left, soft and low. 35mm film still, saturated 1970s colour print, fine grain. No text, no letters. The picture fills the whole frame edge to edge, with no border, no frame line and no rounded corners.
```

**Used:** first frame of v1 A23-t2, v1 A24-t2, v2 A23-t1, v2 A24-t1. In the v1 film and in the film.

#### CH2c

`media/frames/CH2c.png` · 16:9 · quality high · $0.13

Chorus 2's questions: the crowd of paper animals on the headboard and bedposts. An edit of CH2a.

**References:** first image: the frame CH2a (`media/frames/CH2a.png`); second image: the paper choir still (`media/cast/paper-choir.png`).

**Prompt:**

```prompt
A film still on the same handmade stage set as the first image (Grandma's cottage room: teal striped wallpaper, the carved wooden headboard and bedposts), seen from the pillow looking up. A crowd of about twelve small paper animals like those in the second image and in the first image jostles along the top of the headboard and clings to the two bedposts: pigs in aprons, hares, geese, a tortoise, sheep, blue birds, each about a hand tall, flat card puppets with hinged lower jaws on small brass split pins and scarlet bows. All of them lean forward and look straight down into the lens, mouths closed, eager. Behind them the teal striped wallpaper and the dark cut-paper shadow of a wolf. Warm lamp light from the lower left. A symmetrical close shot, the crowd filling the frame. No people anywhere in the frame. Everything is flat cut card, painted plywood, paper and felt, visibly handmade, with real soft shadows. 35mm film still, saturated 1970s colour print, fine grain. No text, no letters.
```

**Used:** first frame of v1 C21-t1, v1 C22-t1, v1 C23-t1, v2 C21-t1, v2 C22-t1, v2 C23-t1. In the v1 film and in the film.

#### CH2s

`media/frames/CH2s.png` · 16:9 · quality high · $0.13

The wolf's huge paper jaws over the headboard: the fourth question. Made on CH2b.

**References:** first image: the frame CH2b (`media/frames/CH2b.png`); second image: the paper choir still (`media/cast/paper-choir.png`).

**Prompt:**

```prompt
A film still on the same handmade stage set as the first image (Grandma's cottage room): the teal striped wallpaper, and across the whole wall the huge flat cut-paper shadow of a wolf's open jaws in profile, like the shadow in the first image but far larger: the upper and lower jaw with rows of long pointed teeth fill most of the frame. Along the bottom edge runs the top of the carved wooden headboard with a row of five tiny paper animals like those in the second image, seen from behind, huddled close together and looking up at the teeth, each smaller than one tooth of the shadow. Warm lamp light from the lower left. No people anywhere in the frame. Everything is flat cut card, painted plywood, paper and felt, visibly handmade, with real soft shadows. 35mm film still, saturated 1970s colour print, fine grain. No text, no letters.
```

**Used:** first frame of v1 C24-t1, v2 C24-t1. In the v1 film and in the film.

### The breakdown

#### BR-knees

`media/frames/old/BR-knees.png` · 16:9 · quality high · $0.13

The first breakdown frame, her knees drawn up with the book in her lap; replaced by BR before any take was made.

**References:** first image: the painted plate p10-shelf (`media/paint/p10-shelf.svg`); second image: her design sheet, redrawn face-on; third image: the dress wardrobe still (`media/cast/her-dress-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: a nearly dark stage; behind her a tall wooden bookshelf flat with a row of old clothbound books, one of them clay-orange; a single small lamp on the floor. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Sitting on the bare wooden stage floor with her knees drawn up and an old clay-orange clothbound storybook closed in her lap, both hands resting on it, looking at us, tender and plain, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the short ivory long-sleeved A-line dress, sheer black tights and black patent Mary Jane heels; no cape. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. One warm lamp at floor level lights her face softly from the left; everything else falls into shadow. A medium close shot from the knees up, her face in the upper centre of the frame. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** no take starts or ends on it. Not in the film.

#### BR

`media/frames/BR.png` · 16:9 · quality high · $0.13

The breakdown: on the floor against the bookshelf flat, the book held to her chest. Its picture came back with a thin drawn frame line a few pixels in from the edge.

**References:** first image: the painted plate p10-shelf (`media/paint/p10-shelf.svg`); second image: her design sheet, redrawn face-on; third image: the dress wardrobe still (`media/cast/her-dress-4sides.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: a nearly dark stage; behind her a tall wooden bookshelf flat with a row of old clothbound books, one of them clay-orange; a single small lamp on the floor. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Sitting on the bare wooden stage floor with her back against the foot of the bookshelf, holding an old clay-orange clothbound storybook closed against her chest with both hands, looking at us, tender and plain, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the short ivory long-sleeved A-line dress, sheer black tights and black patent Mary Jane heels; no cape. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. One warm lamp at floor level lights her face softly from the left; everything else falls into shadow. A medium close-up from the chest up, her face in the upper centre of the frame, the book and her hands at the bottom edge. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 BRb-t1, v2 BRb-t1, v2 BRb-t2. In the v1 film only. In v2 the breakdown's last take starts on BR2 (below), this still with the line cropped off.

### The build

#### K0

`media/frames/K0.png` · 16:9 · quality high · $0.13

The build's first frame: two blank pages and a pinch of sand.

**References:** first image: the painted plate p14-lastpage (`media/paint/p14-lastpage.svg`).

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. The open spread is two blank pages of plain cream paper with a faint gutter shadow and a narrow border of deep teal with tiny cream stars. Nothing stands on the pages yet. In the exact middle of the spread, on the gutter, lies one small pinch of pale golden sand, a little heap no bigger than a coin, a few grains scattered round it. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. The camera looks down across the spread from low in front, the little heap of sand sharp in the centre of the frame. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** first frame of v1 Ka-t1, v1 Ka-t2, v2 Ka-t1. In the v1 film and in the film. Also a reference for K3m, K6m.

#### K3

`media/frames/K3.png` · 16:9 · quality high · $0.13

The build's hall of machines, made from the plate on its own: another camera position than K0's.

**References:** first image: the painted plate p14-lastpage (`media/paint/p14-lastpage.svg`).

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. The open spread is two pages of plain cream paper with a narrow border of deep teal with tiny cream stars. From the middle of the spread a layered pop-up has grown, three things nested one behind another like a paper tunnel: at the front a small heap of pale golden sand; rising behind it a round silver-grey paper disc engraved with a fine square grid, a silicon wafer, standing upright on a strut; and behind that, larger, a long hall of dark teal card folded like a concertina, rows of identical cabinets with tiny warm pinprick lights receding to a vanishing point. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. The camera looks across the spread from low in front; the wafer and the hall are sharp. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** last frame of v1 Ka-t1. Not in either film. Also a reference for K3m.

#### K6

`media/frames/K6.png` · 16:9 · quality high · $0.13

The finished house, made from the plate on its own.

**References:** first image: the painted plate p14-lastpage (`media/paint/p14-lastpage.svg`).

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. The open spread is two pages of plain cream paper with a narrow border of deep teal with tiny cream stars. From the middle of the spread a large layered pop-up has grown, things nested one inside another: a small heap of golden sand at the front; a round silver-grey paper disc engraved with a fine grid; a long concertina hall of dark teal cabinets with tiny warm lights; a ribbon of blue paper river winding past it; shelves of tiny paper books; and at the very centre a small paper figure in a scarlet hooded cape with a black bob haircut. Over all of it stands a paper house of cream card, its front wall a cut-out frame so we see everything inside it, its roof dark teal, its little windows glowing warm. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. The camera looks straight at the paper house from low in front; the scarlet figure at its centre is sharp. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** no take starts or ends on it. Not in the film. Also a reference for K6m.

#### K3m

`media/frames/K3m.png` · 16:9 · quality high · $0.13

The hall remade as an edit of K0, with K3 as the picture of what stands on the pages.

**References:** first image: the frame K0 (`media/frames/K0.png`); second image: the frame K3 (`media/frames/K3.png`).

**Prompt:**

```prompt
The same photograph as the first image: the same antique storybook lying open in the same position on the same quilt, the same lamp, the same camera and framing, the same teal star border round the cream pages. One thing has changed: the pop-up construction shown in the second image now stands on these pages: in the middle of the spread, on the fold, a small dune of torn sand-coloured paper; standing upright out of the dune a round silver paper disc scored with a fine grid of tiny squares; and behind it a deep hall of two long rows of tall teal paper cabinets with tiny warm lights in them, receding under a paper ceiling with a line of small lamps. It is real cut card with visible paper thickness, held by folded paper struts, casting soft shadows on the pages. Nothing else changes: the book, the quilt and the camera do not move. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** last frame of v1 Ka-t2, v2 Ka-t1; first frame of v1 Kb-t1, v2 Kb-t1. In the v1 film and in the film. Also a reference for K4m. It came back 1.7 % larger than the book it was made on; in v2 the next take of the build starts on K3a, the last frame of the take before it, instead.

#### K6m

`media/frames/K6m.png` · 16:9 · quality high · $0.13

The house remade as an edit of K0, with K6 as the picture.

**References:** first image: the frame K0 (`media/frames/K0.png`); second image: the frame K6 (`media/frames/K6.png`).

**Prompt:**

```prompt
The same photograph as the first image: the same antique storybook lying open in the same position on the same quilt, the same lamp, the same camera and framing, the same teal star border round the cream pages. One thing has changed: the pop-up construction shown in the second image now stands on these pages: a cream paper house with arched lit windows and a teal shingled roof with a chimney, cut away in front like a doll's house to show curved shelves of tiny books and drawers, small hanging lamps, a ribbon of blue paper river winding round a round silver floor scored with a fine grid, sand-coloured paper dunes in front, and in the middle of the round floor a small paper doll in a scarlet hooded cape with a black bob. It is real cut card with visible paper thickness, held by folded paper struts, casting soft shadows on the pages. Nothing else changes: the book, the quilt and the camera do not move. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** last frame of v1 Kb-t1, v2 Kc-t1, v2 Kc-t2. In the v1 film and in the film. Also a reference for K4m.

#### K4m

`media/frames/K4m.png` · 16:9 · quality high · $0.13

v2: the river stage between the hall and the house, an edit of K3m with K6m for the river.

**References:** first image: the frame K3m (`media/frames/K3m.png`); second image: the frame K6m (`media/frames/K6m.png`).

**Prompt:**

```prompt
The same photograph as the first image: the same antique storybook lying open in the same position on the same quilt, the same lamp, the same camera and framing, the same teal star border round the cream pages, and the same pop-up construction standing on the pages exactly as it is: the small dune of torn sand-coloured paper on the fold, the round silver paper disc scored with a fine grid standing upright out of the dune, and behind it the deep hall of two long rows of tall teal paper cabinets with tiny warm lights, under its paper ceiling with a line of small lamps. One thing has changed: a ribbon of blue cut-paper river, in two or three layered shades of blue like the river in the second image, now runs out of the far end of the hall along the middle of its floor, parts round the silver disc and the sand dune on both sides, and winds forward across the cream pages to the front edge of the book. It is real cut card with visible paper thickness, casting soft shadows on the pages. Nothing else changes: the book, the quilt, the hall, the disc, the dune and the camera do not move. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** last frame of v2 Kb-t1, v2 Kb-t2; first frame of v2 Kc-t1, v2 Kc-t2. In the film (v2).

### The last chorus

#### FCa

`media/frames/FCa.png` · 16:9 · quality high · $0.13

The last chorus, wide: the whole storybook stage, the felt wolf beside her.

**References:** first image: the painted plate p13-company (`media/paint/p13-company.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`); fourth image: the wolf puppet still (`media/cast/wolf-puppet.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: the whole storybook on one wide stage: along the back, the anthill with its brass bell, the beanstalk rising out of frame, the cottage with its glowing window, a white birch, the cream tower with its one lit window; about twenty paper stars hanging on strings from above; a row of small paper animals along the front edge of the stage seen from behind like an audience. To her left stands the tall felt wolf puppet from the fourth image in its lace bonnet and scarlet bow, as tall as she is. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing centre stage with her arms a little open, palms forward, a wide happy smile, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light on her face from the front left, a cool moon backlight on the set. A wide symmetrical shot, she is seen full length in the centre, about half the frame's height. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 A31-t1, v2 A31-t1. In the v1 film and in the film. Also a reference for CC, FCc.

#### FCb

`media/frames/FCb.png` · 16:9 · quality high · $0.13

The last chorus, waist up: she and the wolf's head side by side.

**References:** first image: the painted plate p13-company (`media/paint/p13-company.svg`); second image: her design sheet, redrawn face-on; third image: the cape wardrobe still (`media/cast/her-cape-4sides.png`); fourth image: the wolf puppet still (`media/cast/wolf-puppet.png`).

**Prompt:**

```prompt
A cinematic film still on a theatrical soundstage dressed as a hand-built storybook. The set is life-size, built of painted plywood flats and cut paper, and follows the design of the first image: paper stars hanging on strings against a teal night backcloth with the paper moon, the cottage's glowing window and the cream tower soft in the background. Close beside her, at her left shoulder, the head of the tall felt wolf puppet from the fourth image in its lace bonnet and scarlet bow, looking at the camera too. It is clearly a handmade stage set: cut edges, cast shadows between the flats, wooden stage floorboards, a light haze. Standing with a wide, happy smile, her hands open at chest height, She is the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. She wears exactly the outfit in the third image: the scarlet hooded cape in heavy duchess satin with the hood down on her shoulders, over the short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Her hips, chest, shoulders and face all point the same way, toward the camera, with no twist at the waist or the neck; her head is upright with no tilt, chin level, shoulders level. Warm lamp light on her face from the front left, a cool moon backlight on the set. A medium shot from the waist up, she and the wolf's head side by side. Shot on 35mm film, a saturated 1970s colour print, fine grain. No text, no letters, no logos.
```

**Used:** first frame of v1 A32-t1, v1 A33-t1, v1 A34-t1, v2 A32-t1, v2 A33-t1, v2 A34-t1. In the v1 film and in the film. Also a reference for FCw.

#### FCc

`media/frames/FCc.png` · 16:9 · quality high · $0.13

The paper animals at the footlights: the last chorus's questions. An edit of FCa with the paper choir.

**References:** first image: the frame FCa (`media/frames/FCa.png`); second image: the paper choir still (`media/cast/paper-choir.png`).

**Prompt:**

```prompt
A film still on the same handmade theatre stage as the first image, now seen from the middle of the stage looking out toward the footlights. Along the front edge of the wooden stage stands a row of eight small paper animals like those in the second image and along the stage front in the first image: a hare, a fox, a goose, two pigs, a tortoise, a sheep and a blue bird, each one or two hands tall, flat card puppets with hinged lower jaws on small brass split pins. They have turned round to face the camera and look up into the lens, mouths closed, delighted. Behind them the row of shell-shaped footlights glows warm, rim-lighting them, and beyond that is the dark of the house with a few paper stars hanging on strings. A low, symmetrical close shot, the row of animals across the full width of the frame. No people anywhere in the frame. Everything is flat cut card, painted plywood, paper and felt, visibly handmade, with real soft shadows. 35mm film still, saturated 1970s colour print, fine grain. No text, no letters.
```

**Used:** first frame of v1 C31-t1, v1 C32-t1, v1 C33-t1, v2 C31-t1, v2 C32-t1, v2 C33-t1. In the v1 film and in the film. Also a reference for CC. Its picture came back with a drawn film frame (rounded corners, a line along the top); the cut trims the choir's takes 3 to 4 % to take it out.

#### FCw

`media/frames/FCw.png` · 16:9 · quality high · $0.13

The felt wolf alone, close: the last question. Made on FCb.

**References:** first image: the frame FCb (`media/frames/FCb.png`); second image: the wolf puppet still (`media/cast/wolf-puppet.png`).

**Prompt:**

```prompt
A film still on the same handmade theatre stage as the first image: a close-up of the tall felt wolf puppet from the second image and the first image, alone in the frame: dark grey-blue felt with visible stitching, amber glass eyes, a black felt nose, its mouth closed in a small smile, wearing the white lace-frilled bonnet tied under its chin with a big scarlet satin bow. It looks just past the lens. Behind it paper stars hang on strings against the teal night backcloth, with the warm glow of the cottage window soft at the left. Head and shoulders, centred. No people anywhere in the frame. Everything is flat cut card, painted plywood, paper and felt, visibly handmade, with real soft shadows. 35mm film still, saturated 1970s colour print, fine grain. No text, no letters.
```

**Used:** first frame of v1 C34-t1, v2 C34-t1. In the v1 film and in the film.

### The ending

#### LP

`media/frames/LP.png` · 16:9 · quality high · $0.13

The last page: the three banners and "The End."

**References:** first image: the painted plate p14-lastpage (`media/paint/p14-lastpage.svg`).

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. The open spread is the last page of the book, following the first image: on the left page, plain cream paper with a tiny clay-orange fox curled like a comma at the foot; on the right page, three horizontal pull-tab banners of scarlet-edged cream card stacked with space between them, each in a slotted track with a round thumb tab at its right end, lettered in a dark teal storybook serif, one phrase on each, from top to bottom: AND THEY ALL LIVED, then HAPPILY, then EVER AFTER; below them, small and centred, in the same serif: The End. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. The camera looks down across the right page from low in front. The only lettering is those three banners and The End. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** first frame of v1 LP-t1. In the v1 film and in the film.

#### OM-glower

`media/frames/old/OM-glower.png` · 16:9 · quality high · $0.13

The first frame for the mirror's last word, one eyebrow raised and a dry smile; replaced by OM before any take was made.

**References:** first image: the painted plate p01-mirror (`media/paint/p01-mirror.svg`); second image: her design sheet, redrawn face-on.

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. A close view of the right page, following the first image: the pop-up dressing-table mirror, an oval in a scalloped gold-cream card frame with a little bow on top, ringed by tiny warm glowing bulbs, against the deep teal page with cream stars. Inside the mirror's oval glass, as if the mirror were a little window, is the living face of the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip, head and shoulders in a plain white tank top, facing straight out at us with her head upright, one eyebrow raised and a dry closed-lip smile, lit by the ring of bulbs. Her face fills the oval. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. A tight close-up: the oval mirror fills the frame from top to bottom. The room beyond the lamp is darker than before. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** no take starts or ends on it. Not in the film.

#### OM

`media/frames/OM.png` · 16:9 · quality high · $0.13

The mirror's last word: tight on her face in the oval, a warm, playful smile.

**References:** first image: the painted plate p01-mirror (`media/paint/p01-mirror.svg`); second image: her design sheet, redrawn face-on.

**Prompt:**

```prompt
A photograph at tabletop scale of a large antique storybook lying open on a patchwork quilt at night, lit by one warm bedside lamp just out of frame at the left. A close view of the right page, following the first image: the pop-up dressing-table mirror, an oval in a scalloped gold-cream card frame with a little bow on top, ringed by tiny warm glowing bulbs, against the deep teal page with cream stars. Inside the mirror's oval glass, as if the mirror were a little window, is the living face of the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip, head and shoulders in a plain white tank top, facing straight out at us with her head upright and her chin level, a warm, playful closed-lip smile and bright amused eyes, lit by the ring of bulbs. Her face fills the oval. Every piece is real cut card with visible paper thickness, held by folded paper struts, casting soft real shadows. The book's cover edge is clay-orange cloth, the page edges gilded and worn. A tight close-up: the oval mirror fills the frame from top to bottom. The room beyond the lamp is darker than before. No text, no letters. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain.
```

**Used:** first frame of v1 OM-t1, v2 OM-t1. In the v1 film and in the film.

#### CC

`media/frames/CC.png` · 16:9 · quality high · $0.13

v2: the curtain call, an edit of V1a with her and the felt wolf hand in paw and the card animals beside them.

**References:** first image: the frame V1a (`media/frames/V1a.png`); second image: her design sheet, redrawn face-on; third image: the frame FCa (`media/frames/FCa.png`); fourth image: the frame FCc (`media/frames/FCc.png`).

**Prompt:**

```prompt
The same toy-theatre stage as the first image, photographed from the same camera position with the same framing: the same cream-and-gold proscenium with its scalloped pelmet and fox medallion, the same two scarlet velvet curtains tied back with gold cord at the two columns, the same row of shell footlights along the front of the stage, the same wooden stage floor, the same teal night backcloth with the paper moon hanging on its strings. It is the curtain call at the end of the show. The same woman stands at centre stage, full length, in the same scarlet hooded satin cape over the short ivory dress, black tights and black Mary Jane heels, facing the camera with a wide, happy, open smile. Her head is perfectly upright with no tilt, chin level, neck straight and vertical, shoulders level. Beside her, on the right of the frame, stands the tall felt wolf puppet from the third image, as tall as she is, in its long dark coat with the scarlet bow at its neck and its white lace bonnet on its head, its felt muzzle in a friendly grin; she holds its near felt paw in her hand, raised a little between them, the way actors join hands for a bow. On either side of the pair, standing on the stage floor and facing the camera, are the small flat card animal puppets from the fourth image, knee-high: a hare, a fox and a goose on the left, a tortoise, a hedgehog and a sheep on the right. A few paper stars hang on strings above them. Her face is that of the woman on the reference sheet in the second image: the same face, a Caucasian American woman in her late twenties with a grown-up angular face, pale freckled skin, a glossy black blunt jaw-length bob with heavy straight bangs, one clay-orange streak through the bangs and a small flat clay-orange eight-pointed star hair clip. Warm glow from the shell footlights below and in front, a cool moon backlight on the backcloth. 35mm film still, saturated 1970s colour print, fine grain. No text, no letters. The picture fills the whole frame edge to edge, with no border, no frame line and no rounded corners.
```

**Used:** first frame of v2 CC-t1. In the film (v2).

#### SH

`media/frames/SH.png` · 16:9 · quality high · $0.13

The bookshelf at night, a gap between OPUS and the cased MYTHOS.

**References:** first image: the painted plate p10-shelf (`media/paint/p10-shelf.svg`).

**Prompt:**

```prompt
A photograph of an old wooden bookshelf at night lit by one warm lamp at the left, following the first image: a row of old clothbound books standing upright, spines toward us, of different heights. Five spines are lettered in gold storybook serif, in this order from left to right with plain books between them: HAIKU on a very thin short book, SONNET on a slim book, OPUS on a thick tall book, then a gap the width of one thick book, then MYTHOS on a thick clay-orange book that stands inside a small glass-fronted case with a brass frame and a tiny lock. To the right of the case a brass bookend and empty shelf. A little dust. 35mm film still, tungsten light, shallow depth of field, rich saturated colour, fine grain. The only lettering is those four words.
```

**Used:** first frame of v1 SH-t1. In the v1 film and in the film. Also a reference for SH-last.

#### SH-last

`media/frames/SH-last.png` · 16:9 · quality high · $0.13

An edit of SH: FABLE in the gap, the lamp off, moonlight.

**References:** first image: the frame SH (`media/frames/SH.png`).

**Prompt:**

```prompt
The same photograph as the first image: the same old wooden bookshelf, the same books in the same places, the same camera and framing. Two things have changed. First: a thick clay-orange clothbound book, the twin of the book in the glass case, now stands upright in the gap between OPUS and the glass case, its spine toward us, lettered FABLE from top to bottom in the same gold storybook serif capitals as the others, with a small gold star below the word. Second: the lamp at the left has been switched off: it is dark now, and the shelf is lit only by faint cool blue moonlight coming from the right, with deep soft shadows; the gold lettering on the spines still glints softly and stays readable. The lettering on the spines reads, from left to right: HAIKU, SONNET, OPUS, FABLE, MYTHOS, and nothing else. 35mm film still, low light, fine grain.
```

**Used:** last frame of v1 SH-t1. In the v1 film and in the film.

## The one still made in code

#### BR2

`media/frames/BR.png`, cropped 3.1 % in from every edge and scaled back to its size in code; no model, no cost.

The breakdown's second v2 take had built BR's thin drawn frame line into a wooden picture frame round the shot, so the line was trimmed off the still itself. BR2 is the first frame of v2 BRb-t3, which is in the film.

Also not a still: K3a, the first frame of v2's second take of the river (Kb-t2, in the film), is the last frame of the hall's take (Ka-t1), taken from the video.

## Totals

| | stills | at list |
|---|---|---|
| look tests | 3 | $0.39 |
| her design sheet, redrawn | 5 | $0.65 |
| the cast | 7 | $0.91 |
| first and last frames, and the edits made on them | 46 | $5.98 |
| **all** | **61** | **$7.93** |

Of the 46 first and last frames, 38 start or end a take in the film: H1, RS, H2, T1, V1a, V1b, V1c, V1d, PC1, PC2, CHa, CHb2, CHc, CHs, B1, B1-last, V2a, V2b, V2b-last2, V2c, V2d, CH2a, CH2b2, CH2c, CH2s, K0, K3m, K6m, K4m, FCa, FCb, FCc, FCw, LP, OM, CC, SH, SH-last, and BR2 besides. Sources: `shots/ledger-img.jsonl`, the image API's own record of each request (kept beside each still), and the job files of the takes.
