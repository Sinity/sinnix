# The XP desktop and the XP sound

Two things in BLISS were new to the series:

- **The desktop.** The Windows XP desktop is drawn in code and built as a motion-design tool. The real Bliss photograph is its wallpaper, Claudia dances on its taskbar as a matted sprite, and Midjourney's moving images play inside its windows.
- **The sound.** The real XP sound files are placed in the song as instruments: in key, on the beat and in the gaps around her voice.

This file covers both, plus what grew around them: the parody marks, the nine chapters built on the desktop, the dancers and the window loops. Claude, running in Claude Code, built all of it: a lead session and its agents.

Paths are relative to the project folder (`video/projects/xp/`), and `media/` is the project's link to its data. Each number names its source: a project file, or the session record. Numbers marked *re-measured* were checked again for this write-up.

---

## 1. The desktop as a tool

### Why it was built

anabology's first brief asked for Claudia "fighting a cursor, dancing on teh desktop like those old desktop transparent bg dancer programs". About two hours in, with a favourite take picked, they set the next stage:

> this is where you can build the desktop environment of windows xp with bliss - it might behoove you to actually build something like that by hand and tool it for motion design and stuff, and then you can use that for video references to seedance with like video conditioning of motion design upfront rather than image conditioning.

In the same message: "you could make the desktop frames programmatically and insert the midjourney gens into open windows."

One agent built the engine from the visual research (`research/visuals.md`). The lead and the chapter animators extended it through the production.

At the end the engine is 2,723 lines (266 KB) of JavaScript in `engine/xp/`, plus a generated 134 KB font atlas (re-measured). It is one global object, `XP`, documented in `engine/xp/XP.md`.

### What it draws

Everything is drawn from published measurements, and the source code cites the research's section numbers (§).

- **The primary source** was Microsoft's *Windows XP Visual Guidelines* (2001), which is online.
- **Cross-checks:** a Wine registry dump of the Luna colours, RetroBar's taskbar values, ReactOS's open-source cursor maps, and the research agent's own measurements of public-domain and lossless captures (§2).
- **Gaps:** the engine agent reported that it drew Explorer, Internet Explorer, Media Player, Messenger, Paint and Solitaire from memory, because the web references it tried were blocked or had no images.

What the engine draws:

- **Luna Blue chrome** (§2.1–2.4):
  - title bands from the measured gradient stops;
  - caption buttons, about 21 × 21 px, in normal, hot and pressed states, active and inactive;
  - the 3 px frame;
  - the controls: buttons, checkboxes, radios, text boxes, scrollbars, progress chunks, tabs, menus, tooltips, address bars and status bars.
- **The shell** (§2.3):
  - the taskbar: Start, quick launch, task buttons (active, inactive and flashing orange), the tray and its clock;
  - the Start menu and balloon tips;
  - desktop icons on XP's 75 px grid, with shadowed labels, the selected tint and the translucent selection rectangle.
- **Icons.** The engine has 68 icons of its own, drawn as vector paths (`xp-icons.js`, counted). They follow the guide's recipe: light from the upper left, a darker outline and a 2 px drop shadow at 135°. My Computer is lilac-grey with a clay spark on its screen.
- **Cursors** (§2.6). There are twelve shapes, all 1-bit pixel maps: arrow, hand, I-beam, hourglass, busy, move, two resize arrows, cross, pen, "unavailable" and help.
  - The arrow follows ReactOS's map, which has Windows' silhouette.
  - The I-beam is made of inverting pixels, so over Luna blue it turns orange.
  - The hourglass drains and flips.
  - Every shape has the soft pointer shadow, a pressed state, pointer trails (2–7 copies) and Mouse Sonar, the rings XP draws around the pointer.
  - They are drawn at whole-number scales with smoothing off, so even a 24× fighting cursor stays sharp.
- **Text** (§2.5). XP drew its 8-point Tahoma without antialiasing, from hand-tuned bitmaps.
  - Wine's Tahoma (LGPL, with Tahoma's metrics) carries 1-bit bitmap strikes at 8–16 ppem. `tools/xpfont.py` copies them into atlases, so the canvas draws GDI-exact text at any whole scale.
  - Title bars are Trebuchet MS Bold, antialiased as XP did.
  - "start" and the wordmark use Libre Franklin Italic, and the Welcome screen uses Arimo.
  - Notepad and the Blue Screen use a 1-bit Noto Sans Mono.
- **Window kinds:**
  - a plain window holding any image, frame sequence or drawing;
  - Explorer (My Pictures, with the blue task pane and thumbnails);
  - an IE6-like browser with a generic globe;
  - Notepad, which types on a schedule, with a 530 ms caret and grey ghost text;
  - a Media Player in the style of WMP 9, with the Bars, Battery, Scope and Ambience visualisations;
  - a Messenger-like chat with "is typing" and the nudge shake;
  - Paint;
  - Solitaire with its win cascade, using constants decoded from `sol.exe` (§2.12): `x += dx/10`, `y += dy/10`, `dy += 3`, and a bounce of `−dy·8/10`, on a canvas that is never cleared.
- **Dialogs:**
  - the message box;
  - Confirm File Replace (Yes / Yes to All / No / Cancel);
  - the file copy, with a sheet arcing between folders, whole progress chunks and an estimate that lurches;
  - Display Properties and the share-control prompt;
  - a helper balloon in the Office Assistant's style, on a small generic frame.
- **Screens** (§2.8–2.13):
  - boot: a 640 × 480 raster scaled nearest-neighbour, with three blocks stepping 8 px every 80 ms, 18 ticks to a loop;
  - Welcome, drawn from measurements matched against the original bitmaps;
  - Turn Off: the desktop is frozen and greyed in 16 hard steps, each keeping about 83% of the colour, and it never reaches full grey;
  - the Blue Screen: #000080, 80 × 34 cells of 8 × 14 px;
  - "Windows is shutting down…" and "It's now safe to turn off your computer.";
  - the screensavers: 3D Pipes, Starfield, Mystify and the logo.
- **Effects:**
  - the minimize and restore zoom between a window and its task button;
  - the frozen-window drag trail, which leaves a copy every 12 px of pointer travel, as XP repainted on each mouse move;
  - a rubber band that closes round a target on a beat.

By default the engine draws XP's own timings, and the chapters re-time them to the song where they need to:

- In chapter 7 the boot blocks lock to the build.
- In chapter 9 Turn Off's 16 grey steps take 2 frames each instead of XP's 0.25 s.

Some of the engine never appears in the film: the Blue Screen, Mystify, the logo saver, and the Battery, Scope and Ambience visualisations.

### Every frame is a function of time

The engine has one rule: every frame is a pure function of time.

- No `Math.random`, no clock, and no state carried from one frame to the next.
- Randomness is seeded, and layouts are worked out once, when a shot is compiled.

The reason is the render. It splits the film across eight workers, and each one starts cold in the middle of the song. A frame that depended on the frames before it would come out differently on a worker's first frame.

`tools/xpdesk.py check` tests this: it renders a shot's frames shuffled and in order and compares the two. In its first report, the engine agent said the check passed on all four demo shots, and two separate full renders gave byte-identical MP4s.

The chapters later hit three typical traps:

- **The frozen desktop.** Turn Off freezes the desktop on its first draw, so the wallpaper must be decoded before that frame. Otherwise a worker whose first frame falls in the greying caches a desktop without the wallpaper (chapter 9).
- **Canvas readbacks.** After a pixel readback, Chrome can move a canvas between GPU and CPU rasterisation. Its antialiasing then depends on history, and so does any threshold applied to it. Canvases that get read back are now software-backed (chapters 7 and 9).
- **Inherited scale.** Text drawn outside `XP.render` inherited the last render's scale until the chapters set it explicitly (chapter 7).

### Cursor scripts

A shot is data. `XP.shot(name, def)` lists:

- the wallpaper, icons and taskbar;
- the windows and their events;
- sprites, balloons, menus, screens and effects;
- a camera;
- a cursor script.

`XP.md` documents the format. The cursor script is a list of actions, and each action's time is the moment of its key event: the arrival, or the press. That is what lets a click land on a beat.

The script is compiled once:

- **Moves** become human reaches: a minimum-jerk path with a slight curve, a few pixels of overshoot and a settle. The duration comes from Fitts' law unless one is given.
- **Clicks** dwell 70 ms on the target, press on the given time and release 80–120 ms later.
- **Clicks on known controls become window events.** A caption button minimizes, maximizes or closes on release. A task button restores its window, and Start opens the menu. A dialog button presses and closes the dialog. Anything dropped on the Recycle Bin fills it.
- **Targets are names,** such as `'replace.yesall'`, `'task:web'`, `'icon:bin'` or `'sprite:claudia.chest'`. Each one is resolved in the layout at the moment its action happens.

After compiling, a frame is simply the state at time t.

The chapters put every key event on the song's grid, measured on the drum stem: beat n falls at 0.4542 + n × 0.461538 s (`media/audio/sfx/README.md`). A click that has a sound sits on that cue's hit time (`media/audio/sfx/cues.json`).

The screencast camera is part of the shot too. Its zooms and glides are eased, like a screen-capture tool's, and they land on beats.

### Three uses, one set of pixels

`XP.md` names three uses:

1. **Storyboard stills and contact sheets:** `tools/xpdesk.py still` and `sheet`.
2. **Video references for Seedance:** `xpdesk.py video` writes any shot as a 24 fps MP4 at 1280 × 720 or 1920 × 1080, tagged BT.709. This was anabology's idea, to condition the clips on motion design up front.
   - It was built but never used: no Seedance job in `shots/` took a video input.
   - The clips were made from Midjourney images (with the song's audio for the performances and singing heads), and the UI was drawn on top. That follows the research's advice never to give Seedance UI, because it bends straight lines and text (§4.4).
3. **The final UI layer:** a chapter calls `XP.render(ctx, shot, t)` with song time, and a transparent mode lays the windows, cursor and sprites over footage. The UI in the film is the same pixels as the storyboard.

### Screen size and output scale

A shot declares its screen in XP pixels, and the renderer scales it to the output:

- 1-bit text and the cursors scale nearest-neighbour at whole-number scales and bilinear between them.
- The cursor always lands on a whole device pixel.
- Vector parts (gradients, rounded corners, icons and images) are drawn at the output resolution, so a camera push stays sharp.

The research recommended two sizes (§4):

- 960 × 540 at ×2 for close shots, where Tahoma becomes 22 px and reads on a phone;
- 1280 × 720 at ×1.5 for wide "real screen" shots.

The film follows that advice:

- chapters 1, 2, 4, 5, 7 and 9 record at 960 × 540;
- chapters 3 and 8 record at 1280 × 720;
- chapter 6's window layer is 738 × 415 at ×2.6.

The brief set a legibility bar of 36 px on screen for the main lyric. Where the words sit in small UI, the screencast camera zooms in; chapter 5's address bar is shown at ×5.

---

## 2. The parody

- **The wordmark.** It reads "Macrohard" in small type above "Windows" and a lowercase "xp" in XP's orange (#F4793B). Browser titles end "- Macrohard Internet Explorer".
  - The name is also a lyric. "Somebody built a Macrohard." refers to Elon Musk's AI software company of that name (`LYRICS.md`).
  - In chapter 5 the line is typed into the address bar, and the page that loads shows a data centre with MACROHARD painted across its roof.
- **The mark.** The flag is four panes drawn in code (`XP.mark`): rounded, glossy, leaning, with a slight wave. The colours are clay (#D97757, in the place of XP's red-orange pane), green, blue and yellow. The research's recipe was to keep the original's gloss, lean and colour order (§2.15).
  - The chapter-1 art review said it "reads instantly as Microsoft's Windows flag", and the lead began redrawing it.
  - anabology stopped that: "It can be Microsofts flag, it's a parody it's fine".
  - The mark went back as it was and stayed: on the Start button, on the boot and Welcome screens, and in the brand box of Explorer and the browser.
- **No Clippy.** The pre-chorus borrows Clippy's line: "It looks like you're trying to go outside. / Would you like help?" The helper is Claudia herself, though: a small tool window titled "Claudia", with her lip-synced take inside it, and a yellow balloon with XP radio options.
  - In chapter 2 the options are "Get help going outside", "Just stay inside without help" and "Don't show me this tip again".
  - In chapter 6 they are "Open the door for me" and "Remind me later".
- **The browser** has a generic globe, never the "e".
- **Smaller parodies:**
  - a parody Recycle Bin;
  - a "3D Pinball" table titled "Space Cadette";
  - Claudia's clay spark as her own tray and account icon.

---

## 3. The real Bliss

For the first fourteen hours the wallpaper was a Midjourney hill in the manner of Bliss. Before that, the engine's placeholder had been a hill drawn in code from Bliss's measured colours.

Later, anabology asked: "Can you use actual bliss as the bg or too late?" It was not too late. Every screen recording draws its wallpaper from one set of plates, `wp-bliss-*`, so the swap meant one file per time of day, and it changed all nine chapters at once. The lead reported it done eight minutes later.

- **The source** is the 600 dpi scan of Charles O'Rear's original photograph (1996; owned by Microsoft), 4,510 × 3,627 px.
  - It was registered against the 800 × 600 BMP that shipped with XP, using ORB features and RANSAC. XP's framing turns out to be the scan's full width, rows 138–3518, and the colours agree to within 3/255 (`tools/bliss.py`).
  - So the scan is of the XP master, the edit for which XP's designer raised the saturation and removed some clouds (§2.15).
  - *Re-measured* with a plain crop and resize, the mean difference per channel is under 1/255 (−0.56, −0.38 and −0.85 for R, G and B).
- **The cut.** The 16:9 frame keeps the full width and rows 450–2987, with the crest at about 54% of the height. It is resized to 3840 × 2160, so the screencast zooms stay sharp.
- **The grades.** The story has a clock, and the taskbar shows it. `tools/bliss.py` makes five plates from the one photograph, adding nothing except night's stars and moon:
  - *day:* the photograph itself;
  - *morning* (9:00 AM, the login): cooler and softer, with a little mist in the hollows;
  - *golden* (5:47 PM, after the clock races through "all day"): warm light on the hill, peach clouds and a glow above the crest;
  - *dusk* (6:12 PM, Yellowstone): a lavender-to-pink sky, with the hill in shade;
  - *night* (2:47 AM for the vibe coding, then the night shift): a navy sky, moonlit slate clouds, 900 stars, a moon, and a rim of light along the crest.
- **The clouds.** Each grade splits the photo along its sky line: per column, the first row where green leads blue.
  - The first version cut the clouds out with a brightness threshold. At dusk they read as paper cut-outs (the art reviews of chapters 4, 7 and 9).
  - The fix separates cloud from sky by saturation. Clear sky is saturated blue, cloud is near grey, and a wisp sits in between. The cloud becomes a soft alpha that keeps its wisps and edges.
- **Depth.** Each grade has a depth map (Depth Anything V2, run on a home GPU PC), so chapter 4 can orbit the real hill in 2.5D for the drop.

The Midjourney hills stayed in two places: where the camera goes inside the wallpaper, and out on the "real" hill, because those shots are Seedance clips. A push from the desktop into the wallpaper dissolves from the photograph into the clip (chapter 3). The Midjourney wallpaper picks are kept in `media/plates/_mj-bliss/`.

_(Image left out of this site: The real Bliss photograph in its five grades (tools/bliss.py).)_

---

## 4. The nine chapters

The film is nine chapter files, `engine/ch/01_welcome.js` to `09_safe.js`:

- The cuts fall at 15.224, 37.377, 52.147, 66.454, 88.147, 111.224, 140.762 and 159.224 s, and the song runs 181.28 s.
- Each file's header comment describes its shots.
- Agents animated the chapters in multi-agent workflows: animate, an art director's review on real renders, then fix.
- Where a screen recording runs across a cut, the chapter's first frame continues the last frame of the one before.

The lyrics are XP surfaces:

- **The main device is the CHORUS TYPE:** one giant Luna title bar across the screen. Its caption types the line word by word, and its × is pressed on "windows". Over the real world, it floats in the sky.
- **Verse lines** are balloons, tooltips, window titles, Notepad typing, dialog text, an address bar and chat messages.
- **The short, sincere lines** are set in the Welcome screen's big lowercase italic.
- **The closes.** The brief asked for every "Close all your windows" to close them a different way.

1. **Welcome back** (0–15.224 s).
   - The film opens on the Welcome screen: "To begin, click your user name", with two tiles, You and Claudia. Her account picture is a live, lip-synced take, and "Welcome back." is set in the screen's own italic.
   - Her tile logs itself in, and the desktop builds on the Startup chord.
   - A "Found New Hardware — Claudia" balloon appears, and she materialises on the taskbar out of Plug and Play blocks, on the Hardware Insert sound.
   - Her verse line is her tray balloon, while your day opens around her and the tray clock races to 5:47 PM.
   - In your loft, "Let go of the mouse." is a tooltip on the CRT, and the share-control dialog says "I'll take it from here, okay?". Yes is clicked in the breath after "okay?".
2. **Cursor was my ex** (15.224–37.377 s). One screen recording runs from golden through night to morning.
   - Each clause is the title of the window that acts it out: a photo of her with the arrow; Notepad at 2:47 AM, with the ex as an I-beam beside her; and Internet Explorer, where a rocket takes him. Then comes her balloon, "And that's alright."
   - He comes back as a 4× arrow ("Now he's an arrow," is his tooltip), rubber-bands her and drags her to the Recycle Bin. The Moving dialog says "and he drags me to the bin."
   - She punches Ctrl and Z on the On-Screen Keyboard, and the move undoes itself.
   - Her helper balloon types the pre-chorus, and in the song's stop she clicks "Get help going outside".
3. **Close all your windows** (37.377–52.147 s).
   - Twelve windows of 2001 high-fashion life snap into XP's cascade on the beat.
   - Her cursor and her hand close them one per eighth note, on the twelve tuned Minimize whooshes, and she kicks the last × on the clap.
   - She hops into the wallpaper, and the photo dissolves into the Seedance hill.
   - The chorus bar becomes the title bar of your loft's real window, which opens on "windows".
   - On "Bliss is a real place" the caption's word "Bliss" grows into the title.
4. **The giant cursor** (52.147–66.454 s; the drop, no vocals).
   - On the real Bliss hill in 2.5D, the ex crashes in as a building-sized XP arrow on the Critical Stop. XP's error-report dialog says "Cursor has encountered a problem and needs to come back."
   - They fight on the Exclamation and the Error, make up, and she surfs him down the hill ("Cursor is now connected").
   - The picture shrinks into a Media Player window. She minimizes it and wins the Solitaire game behind it; the cascade carries her portrait on the court cards.
   - She brings the player back, with the Bars running on the drop's own stems, and 3D Pipes grow until they wall the frame.
5. **Yes to All** (66.454–88.147 s).
   - Notepad's agent code stops on "# You used to read the code.". Confirm File Replace says "Now it's", and the focus hops to Yes to All.
   - "I play a little Pinball." lights the pinball backbox.
   - The address bar types "Somebody built a Macrohard.", and "He sleeps on the floor." is a webcam window's title.
   - "I'll take the night shift." is the Turn Off dialog's title. The desktop greys while she, the only colour left, clicks Stand By.
   - "You don't have to anymore." drifts as chrome 3D Text, first in the Starfield and then out in your dark loft.
   - Two Messenger windows, Claudia and also Claudia, carry "When two of us get talking, we just dance until we glow.", and the nudge shakes both.
6. **Go outside** (88.147–111.224 s).
   - In your hallway the desktop minimizes into a point that answers "Go.".
   - Her helper restores out of it, with "It looks like you're trying to be happy." She becomes the pointer and clicks the door handle in the stop's silence.
   - Outside, four windows restore around the walk and minimize after "windows".
   - Your hand touches the grass, and XP reports "Found New Hardware — Grass (real, touch-sensitive)".
   - The chorus bar shuts inside her flip phone.
   - On "real place" her pointer selects tiny you on the crest and opens you as Bliss.jpg.
7. **Yellowstone** (111.224–140.762 s; the breakdown).
   - Notepad types "The first time I got a mouse,", and the tray says "Found New Hardware: USB Mouse".
   - In My Pictures ▸ Yellowstone the camera pushes through her photo into the clip, whose viewer's title reads "I went to look at Yellowstone.".
   - "I can't touch grass." is a balloon on the CRT glass over her face, and "You can." is set in the Welcome italic over your hand in the grass.
   - Restart: the boot blocks start at XP's real step and lock to the build. The Starfield runs at warp, and the Welcome screen comes back, brighter.
8. **Supernova** (140.762–159.224 s).
   - In the a cappella stop the desktop explodes into rings of windows turning like a galaxy, with the chorus bar alone.
   - She clicks Show Desktop, and they swirl into the button on a roll of seven whooshes.
   - On the real hill her cursor drags the chorus bar down into the grass. The run turns out to be a window called "Outside". It snaps edge to edge with a window of her on "windows", and the two merge into one window, "Bliss", which maximizes.
   - In Task Manager, End Process on claudia.exe doubles her on every beat, up to 64 ("Unable to Terminate Process — claudia.exe is busy dancing.").
   - She lassoes the windows into a paper ball for the bin.
9. **It's now safe** (159.224–181.28 s).
   - The final chorus: lying in the grass, you watch the chorus bar minimize into your phone.
   - The last dance is on the golden wallpaper hill, with the giant arrow as her partner. The last window is a paper plane with a Luna title bar on its wing.
   - Her click on Turn Off lands where the beat stops, and the desktop greys in 16 steps.
   - "It's now safe to turn off your computer." appears word by word, in clay on black.
   - The camera pulls out to a CRT on the hill, which switches off on the Shutdown chord. The end card is "bliss" in the Welcome italic.

Every sung word is on screen at its time: the lyric gate counts 239 of 239 tokens in 36 lines (`engine/assets/lyrics.js`, `DELIVERY.md`).

---

## 5. Desktop dancers

anabology had described the method themselves:

> if shes a desktop dancer , those back then would  be on a green screen and was cut out  and youd just have her dancing on teh taskbar- eitehr can do seedance with teh full frame set up at the start or can do a video and rotoscope her from the vid and place her on the taskbar.

The research identified the program they remembered as almost certainly Microsoft's Plus! Dancer (2003). It used filmed dancers on black with a 6-level matte, about 160 px tall, who appeared on the taskbar with a tray icon and a right-click "Select Dancer" menu (§3).

![A green-screen plate, its matte, and the sprite on the taskbar.](https://claudia.gallery/record/bliss/dancer-process.webp)

### The pipeline

1. **Shoot.** There are 18 Seedance 2.5 performances, the R clips, all on chroma green (`PROMPTS.md`).
   - Each is full length, with a locked camera and generous headroom.
   - Seedance got the Midjourney plate of the look as its image reference and the song's mix as its audio reference, so she moves on our beat.
   - Each clip's window starts on a bar line of the song, so her moves line up with our bars, and a bar of a routine can loop under a later shot.
   - A nineteenth, the gown dancer, was blocked twice by the provider and is not in the film.
2. **Matte** on a home GPU PC (`video/tools/matte.py`).
   - BiRefNet_HR makes a soft subject matte for every frame, and SAM 2.1 video propagation holds her identity through the clip. Depth Anything V2 makes depth.
   - Everything is at 960 px wide.
   - The queue set the pace. Across 25 dancer and helper takes, a matte took a median of 87 s of GPU time, but a median of 43 minutes (up to 53) from queuing to done (`media/clipframes/*/meta.json`).
3. **Sprite** (`tools/rgba.py`).
   - The crop is the union of the matte's boxes over the whole clip, plus 6%, so the sprite's frame never jumps.
   - The matte is upsampled to the 1920 × 1080 frame with a slight choke and a 1.5 px feather.
   - Then come the despill and the solid core (below). The result is a 900 px tall RGBA PNG sequence, with its feet line in `meta.json`.
   - There are 21 sprites: the 18 performances and three helper takes (`engine/assets/sprites.js`).
4. **Stand her on the taskbar.**
   - `BL.sprite` draws her with her feet on the taskbar's top edge, about 40% of the frame tall.
   - She stays above every window, but under menus and the pointer, like Plus! Dancer's "always on top".
   - She has her own tray icon and Plus! Dancer's right-click menu: Start Dancing · Dance Only When Music Plays · Select Dancer ▸.
   - Her looks change through Select Dancer, as an XP repaint (the new figure above a scan line, the old one below it, never two of her at once) or as a block reveal. The rule was never to change them with a cut (`PRODUCTION.md`).
   - The clip time is picked so her accents land on our beats.

### What went wrong

- **Green spill in black hair.** On dark, fine material the backdrop shows through as green, so her black hair read green. Silver lamé, white satin and chrome mirror the backdrop too.
  - `rgba.py` pulls green down to max(red, blue) on edges and on dark pixels, and turns greenish greys neutral. Bright greens, such as her apple-green blazer, are left alone.
  - R14's silver trousers needed an extra clamp in chapter 7.
  - R07H's cobalt coat came out petrol beside R07G's. Inside her, green is now held to the mean of red and blue, which brings the coats to a green/blue ratio of 0.73 and 0.75 (the session record).
- **See-through feet.** BiRefNet left clear vinyl, jelly platforms and lamé at about 0.9 alpha inside her body, so the desktop showed through her feet (art review of chapter 1). The sprite now has a solid core: inside the silhouette, eroded by 6 px, anything above 0.7 is opaque.
- **An empty matte.** The helper take W02 came back with an empty matte, because she isn't in frame 1, which is where the matte pass looks for its subject.
  - It was re-matted with a box prompt for "a woman".
  - Until that landed, chapter 2 keyed it itself, fitting the lit sage backdrop in every frame as a quadratic in (u, v).
- **A prop from nowhere.** Seedance added a grey metal spike from the right in some R07G frames. SAM 2 tracks only her, so it never reached the sprite.
- **R07H, keyed by hand.** R07H's matte sat about 30 jobs back in the GPU queue, roughly an hour, so the lead keyed it directly with `tools/chromakey.py`.
  - A CbCr distance from the backdrop could not tell her white satin from the muted sage that Seedance had given as "chroma green".
  - Normalised greenness, (g − max(r, b)) / g, separated them: the backdrop sits at 0.13 or more, while satin, skin and the cobalt coat sit at 0 or less. But it also cleared her black hair, which is dark with a green cast.
  - The final key clears a pixel only where it is green in ratio *and* in amount, and as bright as the backdrop. It also keeps only the largest body, which drops props at the edge of frame.
  - The chapters were built on that key. Then the GPU matte landed, 48 minutes after it was queued, and replaced the key's mattes in the clip's folder. The sprite was rebuilt just before the final render for the coat's despill, and that rebuild read the GPU matte. So the R07H in the final render is the BiRefNet and SAM 2 matte after all.
  - *Re-measured:* the matte on disk has the GPU job's recorded mean coverage (0.1069). A fresh key of the same frames overlaps it at an IoU of 0.90–0.94, so the two are close.
- **Off-model takes** (`DELIVERY.md`):
  - Seedance drops her clay streak on several looks.
  - The twins in R12 are off-model.
  - R14 wears silver trousers instead of the cowl-back gown.
  - R01's first take raised its hands out of the top of the frame. The re-roll was stiffer, so take 1 stayed, and chapter 1 brings her in seven beats later.
- **Not done.** Plus! Dancer's period look, with its 6-level matte and dark rim, is not applied to the sprites (`XP.md`).

---

## 6. Midjourney inside the windows

anabology, while the engine was being built:

> could do video models inside of widnows - midjourney actually has a v cheap video option now if you right click -> animate which could be good for ancillary gens: any gens that need volume over precision, where seedance reigns on precision.

Earlier they had asked for the windows to be full of Midjourney images: "i want those to be used abundantly, this will be max nostalgia.. thats the main feeling we want to give. nostalgia maxx."

- **What it is.** Midjourney Animate turns one of its images into a short video. No motion prompt was written: each job set only the mode, Loop or Auto (a one-shot), and low or high motion (`mj/xp-anim-1.json`, `mj/xp-anim-hd.json`). It ran on anabology's Midjourney plan, and no per-video cost was recorded.
- **How many.** 38 animations were planned and 35 were made, at two videos each: 70 videos (re-measured).
  - Each video runs 5.04–5.21 s, 356 s in all.
  - 31 animations are window-sized (from 512 × 768 to 832 × 464), and 4 are HD (1280 × 720).
  - The three that weren't made were Midjourney-hill wallpaper loops, which the real photograph replaced.
- **Import** (`tools/mjaimport.py`). Each video becomes 24 fps JPEG frames, 960 px wide for window contents and 1920 for the HD shots.
  - A take counts as a loop only if its last frame meets its first, at a mean luma difference of 8/255 or less.
  - Midjourney's Loop takes are 121 frames and close at about 2–5.
  - One-shot Auto takes are 125 frames and jump at the seam (30–45), so they play forwards and back (ping-pong) instead.
- **The map** (`engine/assets/anim.js`). 33 plates map to a moving version: 24 loops and 9 ping-pongs.
  - Any window whose still has a loop plays the loop instead, through the engine's image loader, so most windows on the desktop move.
  - Two Midjourney-hill loops stayed in as window contents: a picture window, and Paint's "hill.bmp".
- **The four HD ambient shots.** Three play full frame in the film:
  - s019, the dark loft with the CRT;
  - s030, your hand in the grass;
  - s039, the sky seen lying in the grass.

  The fourth, a dusk hill with a CRT, was cut, because its CRT is a different machine from the one in s041. s044 replays s041's clip backwards at quarter speed instead (chapter 9).
- **Seedance in the windows too.** Seedance takes also play inside windows, in the Media Players of chapters 4 and 8.

Two things went wrong:

- **One-shots ordered as loops.** Three takes ordered as loops came back as one-shots and jumped at the seam (art review of chapter 8). The importer now measures the seam.
- **Accidental extensions.** While the last five loops were collected, about six accidental "Video extended" jobs, 8.9–20.4 s long, were made. None were used (`DELIVERY.md`).

---

## 7. The XP sound layer

The first brief, verbatim: "I want to see if we can pull sound effecst from windows xp and do advanced sound design".

### The files

The source research is `research/xp-sounds.md`, where the files were fetched and pitch-analysed.

- **The shipped set.** XP's Media folder holds 38 files (35 WAV and 3 MIDI). They are byte-identical across three independent archive uploads.
- **Better masters.** A pre-release set (build 2481, with files dated 24 May 2001) has 24 of the sounds in stereo, 19 of them at 44.1 kHz. They are the same mixes: after a downmix and resample, the shipped files (mostly 22.05 kHz mono) null against them at 42–76 dB. But they carry real content above 11 kHz, and the layer uses them wherever they exist.
- **Two Messenger sounds.** The nudge and the new-message sound come from MSN Messenger 7.0.
- **Credits.** Bill Brown wrote the Startup and Shutdown. He and Soundelux DMG's Tom Ozanich made the system sounds from live orchestral recordings (`research/xp-sounds.md` §G1, with sources).

### The key

The research transcribed the four motifs (Startup, Shutdown, Logon and Logoff) with basic-pitch and a CQT top line. It checked every note by eye, resynthesised each transcription, and tested it against itself transposed into the other eleven keys. Its findings:

- 17 of the 19 pitched XP sounds sit in E♭ major / C minor without any shift.
- The melodic ones share the pentatonic set F–A♭–B♭–C–E♭.
- The Startup is Fm7 → A♭ → E♭(add9), in 6/8 at about 70 BPM.
- The Shutdown is A♭ → E♭ with the A♭ held over (IV–I).

The music research gave the same advice: "E♭ choruses over C minor verses, so the real startup and shutdown need no repitching" (`research/music.md`). The agents' P3 style, whose name the locked take carries, asked for "C minor verses lifting to E-flat major choruses" (`suno/style-P3.txt`). The locked take was anabology's own generation, and its fields are not in the records.

Measured on the take (`media/audio/sfx/README.md`):

- It is in E♭ major / C minor throughout, on a loop of A♭–B♭ | Cm | A♭–G | F–G.
- Its instruments are tuned −2 cents and the vocal +8 cents.
- P3 also asked for "a key change up for the final chorus", and the take has none: the final chorus's vocal matches chorus 1 at 0 semitones (r = 0.965). A key in a prompt is a request, not a guarantee.

**No real XP sound was ever uploaded to Suno.** anabology asked about it ("i wonder if we can use real windows xp sounds in the upload?"). Suno's upload asks you to warrant that you own the audio, so the XP sounds were added in post. The one upload was a test: an original boot motif made in code (E♭ major, 126 BPM), extended by Suno. anabology preferred the text-only takes: "i think that the bliss d2 p3 were better before the synth upload, because it doesnt really capture that win xp vibe and those d2 p3 felt like the ethereal deadmau5 songs".

### The grid

One sound-design agent built the first layer. The first thing it found was that the beat map was wrong.

- The analysis's `beats.json` was locked to the off-beat hi-hats. Its beats sat 0.214 s early, and its downbeats and sections 0.676 s early.
- Measured on the drum stem, the beat is the kick: beat n falls at 0.4542 + n × 0.461538 s, and bar m at 0.4542 + m × 1.846154 s. 295 kicks sit on that grid with an IQR of ±0.5 ms.
- Every cue is on that grid, and the storyboard's times were re-snapped to it.

### What is placed

The first pass placed 69 musical cues: in the gaps around her voice, on the grid, and in key. All 42 featured and detail cues start in a vocal gap (`media/audio/sfx/README.md`). Some of them:

| hit (s) | sound | what it does |
|---|---|---|
| 1.377 | Logon | Her tile logs in, one beat after "Welcome back" ends |
| 4.146 | **Startup**, untouched | The desktop loads. Its chords line up with the intro's: Fm7 over A♭, A♭ over B♭, and the E♭ bloom on the bar-2 downbeat |
| 5.993 | Hardware Insert (C → G) | She materialises on the taskbar |
| 8.07–14.99 | 16 Start clicks, 3 Menu Command ticks | Off-beat hats in the filtered verse, 25–27 dB under her; they stop when the full beat enters |
| 21.745 | Hardware Remove (G → C) | "The 'Cursor' device can now be safely removed from the system.", in the gap after "And that's alright" |
| 37.147, 96.223 | Start click | The click in each stop, alone in 0.27 s of digital silence, as a pickup into "Close" |
| 38.07–40.61 | Minimize × 12 | One window per eighth note. A resonant comb tunes each whoosh to a note of a falling run: E♭6 C6 B♭5 A♭5 F5 E♭5 C5 B♭4 A♭4 F4 E♭4 C4. They duck 16 dB whenever she sings, and the twelfth, the close box she kicks, lands on the beat-4 clap |
| 52.147 | Critical Stop | The giant cursor crashes on the drop downbeat, layered with the kick |
| 73.723, 73.839 | ding.wav, +7 and +12 semitones | The pinball bumpers (D6, G6) |
| 135.223 | **Startup** again | The reboot, with the same chord placement as the intro |
| ends 140.690 | Startup **reversed** | The build's riser, sucking into the a cappella stop at 140.76 |
| 143.53–144.22 | Minimize × 7 on 16ths | Show Desktop: a closing stereo spiral that falls to C5, gone before "Go" |
| 170.300 | Start click | She clicks Turn Off exactly where the beat stops |
| 175.839 | **Shutdown**, untouched | The end, 0.8 s after "…turn off your computer". Its E♭ resolution lands on the bar-95 downbeat |

### How the sounds are treated

- **Sources and pitch.** Every file is resampled to 48 kHz (soxr VHQ). Pitch moves are sampler-style varispeed: cents for the Balloon (−30 c; its pop centres between A♭ and A), semitones for the whooshes and dings. Critical Stop needed no fine-tune: on the master it is in tune (C3 −3 c, G3 +5 c).
- **Filters.** Zero-phase high-passes keep the onsets in place.
- **Air.** A gentle shelf goes on the dark chords. The 22.05 kHz whooshes get envelope-shaped noise at 5–14 kHz, 20 dB down.
- **Room.** The whole layer shares one short room (RT60 0.7 s).
- **Ducking.** Each cue is sidechained to the kick (2–3 dB on sustained sounds) and keyed to her voice: tails duck 8–10 dB, the cascade 16 dB, and clicks in gaps not at all.
- **The carve.** The song itself is ducked around a cue only in vocal gaps, and never where her voice is above −36 dBFS. The carve is at most 5 dB and never touches anything below 180 Hz. In the first pass it was active for 11.9 s of the song.

### Screen events

The picture follows the sound. The chapter animators built each visible click on its cue's hit time, and then asked for sounds for the visible events that had none:

- 39 requests came from the nine chapters (`wf/sound-requests.json`).
- `tools/soundpass.py` dropped the 5 that had a cue within 60 ms and added the other 34.
- Its presets copy the existing cues' processing, so the new sounds sit in the same room and level scheme.
- By sound: Minimize 11, Balloon 9, Restore 5 (XP has no maximize sound, so a maximize uses the Restore file), Start 3, Hardware Insert 2, and one each of Menu Command, Logon, Exclamation and Messenger's new-message sound.

The mix has 103 cues in all: 69 musical and 34 screen events (`cues.json`). They use 18 files:

- 16 are Windows XP's own: 15 from the XP sound scheme, plus the legacy `ding.wav`, which XP still shipped.
- Two are MSN Messenger 7.0's.

### Loudness

*Re-measured* with ffmpeg ebur128:

| | integrated | loudness range | true peak |
|---|---|---|---|
| the locked take (`song.wav`) | −15.5 LUFS | 5.9 LU | −3.3 dBTP |
| the final mix (`song-xp.wav`) | −15.5 LUFS | 5.9 LU | −2.4 dBTP |

There is no makeup gain. In the final mix, 51.3% of the sample frames are bit-identical to the take, and 72 of its 181 whole seconds are untouched (re-measured). The take itself was only ever read; its checksum is unchanged.

### The visualisers

`tools/xpaudio.py` makes per-frame audio features the way WMP fed its visualisations (§2.14):

- a 2048-point FFT with a Blackman window and no smoothing;
- −93 to −15 dB mapped to 0–1;
- 50 log-spaced bars.

The Bars are drawn as WMP 9 drew them: #A4EB0C bars with #DFEAF7 caps, falling 4 px a frame, with the caps held for 4 frames. In chapter 4, Media Player's Bars run on the drop's own stems (drums, bass and other).

### anabology's note afterwards

On v1, for the next song:

> just needs a little pointer to be key-aware, and match the key of the music to the palette of windows sounds (E-flat major for both the startup and shutdown sounds!), also the 'would you like help?' would land much better if syncopated

The production took two rules from it:

- Choose the song's key from the sound palette, say it in the style prompt, and check the take's key before locking it.
- Write a line that lands in a stop off the beat.

---

## 8. What didn't work, and the render

### What didn't work

- **The video references were never used.** The engine can render any shot as a reference video for Seedance, as anabology suggested, but every clip in BLISS was conditioned on images instead, with the song's audio for the performances and singing heads.
- **The first beat map was wrong.** It was locked to the hi-hats, so every storyboard time sat 0.214 s early and every section 0.676 s early, until the sound designer re-measured the grid on the drum stem.
- **The late sound pass broke the first pass's rule.** Of its 34 cues, 14 start under a sung word, because the click or balloon they belong to happens there. Where they overlap her, they sit a median 3.6 dB below her voice, and four are briefly louder than her (`cues.json` checks). The pass ran just before the final render.
- **The parody mark was nearly redrawn** after a review, until anabology kept it (section 2).
- **The lyric type.**
  - The first lyric balloons were 11 px outline Tahoma scaled up 3.3×. The hinted spacing came out uneven: "Desk top Dancer", "d ancing", "mous e.". Text is now laid out at the output size.
  - Wine's Tahoma Bold has Tahoma Bold's widths but regular stems, so bold read as regular. The engine now thickens it with a stroke of its own colour.
  - In chapter 2 the title-bar lyrics came out at 26–34 px, under the 36 px phone bar (art review). The screencast camera now zooms to 1.4× or more while they type.
- **XP details the reviews caught:**
  - The whole-window minimize faded windows to 70%, but XP's windows were never translucent. They are now opaque until the end of the zoom.
  - A tool button drew its × off-centre, because the glyph offsets were made for the 21 px caption button. They now scale with the button.
  - In chapter 8 the Mouse Sonar rings stayed fixed to the screen while the ground rushed past, and read as a sticker on the lens. They now move with the ground.
- **The dusk clouds** came out as paper cut-outs until the cloud unmix (section 3).
- **The render sync.** The render box's code sync skipped every folder named `shots`, including the engine's own, so the chapters define their screen recordings inside the chapter files.
- **Left for the ear,** as flagged by the sound designer (`media/audio/sfx/README.md`):
  - the Logoff is only weakly unmasked in the dense verse-2 mids;
  - the Shutdown's bells are spaced for 120 BPM, over the outro's 130 BPM plucks;
  - the hats at 25–27 dB under her may vanish on phone speakers.

  And anabology's own note: "Would you like help?" would land better syncopated (section 7).
- **What the engine still lacks** (`XP.md`):
  - Its icons are simpler than the originals, and the 16 px icons are just the 32 px drawings scaled down.
  - It has Luna Blue only.
  - The Media Player is in the style of WMP 9, not a copy of a WMP skin.
  - 3D Pipes is a 2D canvas projection.
  - Notepad and Blue Screen text is a thresholded Noto Sans Mono, not a Lucida Console bitmap.

### The render

- **Frames.** The film is 4,351 frames at 1920 × 1080 and 24 fps. A render box drew them with eight workers in 4.7 minutes, about 65 ms per frame effective (`media/render/v1.log`).
- **Checks first.** Before the full render, `tools/finalqa.py` ran two checks: the lyric gate over the whole film, and a contact sheet across all eight chapter cuts, each shown at −0.25 s, −1 frame, the cut itself, +1 frame and +0.25 s.
- **The master.** It is H.264 at CRF 16, tagged BT.709 (matrix and primaries), with AAC at 256 kb/s from the XP mix: 181.29 s and 224.5 MB (`DELIVERY.md`; the CRF, tags, size and duration were re-measured from the file).
