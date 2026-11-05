# Branding onboarding

Goal: produce `brand/brand.yaml` (plus `brand/logo.png` and `brand/fonts/`) that the user has confirmed. Run this once per brand, before the first render, and again whenever the brand changes.

Walk the user through it one step at a time. Ask one question, wait for the answer, then move on. Keep the tone plain. Never push the user to a step they have no material for.

## Step 0: where to write

Ask: "Which folder is for this brand's files?" Default to `./brand` in the user's project. Use a separate folder per brand or client (`brand-acme`, `brand-plum`). Never write brand files inside this repo.

## Step 1: what do you have?

Ask: "Which of these do you have? You can give me more than one."

- **A** A website URL
- **B** A logo file (PNG, SVG, JPG, WEBP)
- **C** A brand kit: PDF, ZIP, folder, Word doc, or a style guide in text or markdown
- **D** None of these

Sources combine. When they disagree the order is: the user's own answers, then the brand kit, then the website, then the logo palette.

## Step 2: run the extractor

Pick the command that matches what they gave you. Run from the skill's `scripts/` folder through `vs.py`:

| They gave | Command |
|---|---|
| Website | `vs.py brand --url https://their-site.com --out brand` |
| Logo | `vs.py brand --logo path/to/logo.png --out brand` |
| Kit | `vs.py brand --kit path/to/kit.zip --out brand` (also accepts a PDF, DOCX, markdown file, or a folder) |
| Several | Combine flags: `--url ... --logo ... --kit ...` |
| Nothing | Go to Step 3 and use the questions |

What the extractor does:

- **Website**: reads the page and its stylesheets. Takes colors from CSS variables, the theme color meta tag, and the most used chromatic colors. Takes fonts from `font-family` rules, Google Fonts links and `@font-face`. Takes the name, tagline and headlines from page metadata. Finds the logo in the header, an inline SVG, the touch icon, the share image or the favicon (best first), and saves it as a trimmed transparent PNG.
- **Logo**: converts to a trimmed transparent PNG and pulls the dominant colors, ignoring transparent pixels.
- **Kit**: reads text from PDF, DOCX, markdown and similar files. It finds hex and RGB values and the words around them (primary, accent, background, text). It finds font names in the text and in PDF font resources, picks up any `.ttf`, `.otf`, `.woff`, `.woff2` files, and picks the best logo file (SVG first, then names containing primary, full or color).
- **Answers**: `--name`, `--tagline`, `--primary`, `--accent`, `--background`, `--text`, `--heading-font`, `--body-font`, `--cta-text`, `--keyword`, `--tone`, `--handle`.

The command prints a summary and writes `brand/brand.yaml` and `brand/brand-preview.png`.

## Step 3: if they have nothing (D), ask these questions

Ask them one at a time. Skip any the user does not know; the extractor has defaults.

1. What is the business or personal brand called?
2. In one sentence, what do you do and for whom? (becomes the tagline)
3. Pick a main color. Give a hex code, or a plain name ("deep teal", "warm orange"). Convert names to hex yourself and say which hex you chose.
4. Pick a second color for highlights. Same rule.
5. Is your background light or dark? (white `#FFFFFF` or near-black `#0B0F19`)
6. Do you have a font you like? If not: "friendly and rounded", "clean and modern", "classic serif", "bold and loud". Map to Poppins, Inter, Lora, Anton, or pass the exact Google Font name.
7. What should the end of your videos ask viewers to do? ("Follow for more", or a keyword they comment: `GUIDE`.)
8. What is your handle or website, if you want it shown?
9. How would you describe your tone in three words? (stored in `voice.tone`; does not affect rendering.)

Then run: `vs.py brand --name "..." --tagline "..." --primary "#..." --accent "#..." --background "#..." --heading-font "..." --keyword WORD --out brand`

## Step 4: show the result and get confirmation

1. Open or attach `brand/brand-preview.png`. It shows the name, tagline, logo on light and dark chips, the four colors with hex codes, the fonts, the CTA, and a mock 9:16 frame with a caption and the logo placed.
2. Read the summary back in plain words:
   - the four colors and where each came from (`provenance` in the file)
   - the two fonts and whether they are the real brand font or a substitute
   - whether a logo was found
   - every line under `notes`
3. Check these yourself before asking the user:
   - Logo on dark chip is visible. If the logo is dark on dark, tell the user and offer a light version or a background plate.
   - Text color has contrast 4.5:1 or better on the background. The extractor adjusts text if it fails; mention it if it did.
   - The accent differs clearly from the primary.
4. Ask: "Does this look like your brand? Anything to change?" Do not continue until the user says yes.

## Step 5: edits

Apply each change with the edit command, then show the new preview:

```
vs.py brand edit brand --set colors.primary=#E11D48
vs.py brand edit brand --set colors.accent=#F59E0B --set cta.keyword=GUIDE
vs.py brand edit brand --set fonts.heading.family="Montserrat"
vs.py brand edit brand --set logo.position=top-left --set logo.scale=0.2
vs.py brand edit brand --set logo.show_in_videos=false
vs.py brand edit brand --set tagline="Short, true sentence"
```

Changing `fonts.<role>.family` downloads that Google Font. To use a licensed font file the user owns, copy the `.ttf` into `brand/fonts/` and set `fonts.heading.file` to `fonts/YourFont.ttf`.

To replace the logo: `vs.py brand --logo new-logo.png --out brand` (this rewrites brand.yaml from the new source, so re-apply earlier edits), or copy a PNG over `brand/logo.png`.

## Step 6: fonts and licences (say this to the user)

- Google Fonts are open licence and are downloaded automatically.
- A custom font on the user's website is **not** downloaded by default because its licence is unknown. The extractor picks the closest Google Font and writes a note naming both. Tell the user which one it chose.
- If the user owns the licence, they can pass `--allow-site-fonts` (website) or drop the file into `brand/fonts/` (kit or manual).
- Fonts from a brand kit are copied into `brand/fonts/`. Remind the user not to publish that folder in a public repo.

## Step 7: a first test render

Offer a ten-second proof: `vs.py demo --brand brand --out brand-demo --styles list-the-ways --max-seconds 10`. View the stills. Fix anything off with Step 5. Then the brand is done.

## Finish by saying

"Your brand is saved in `<folder>/brand.yaml`. Every template style will use it. To change it later, tell me what to change, or edit the file."

## Failure handling

- Website blocked, empty, or a single-page app that renders in JavaScript: the extractor finds few colors. Say so, then ask for a logo file or the Step 3 questions.
- No logo found: continue without one. `logo.show_in_videos` stays false. Ask for a file.
- Offline: fonts cannot download. Colors and logo still work. Rerun with network, or set font files by hand.
- Logo is JPG with a white background: the extractor makes the background transparent when all four corners match. Check the preview chips.
- Never invent brand data. If a value is unknown, leave the default and say so.
