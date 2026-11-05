# brand.yaml reference

The file lives in the brand folder (default `./brand/brand.yaml`). Paths inside it are relative to that folder. Any field you leave out falls back to `templates/brands/default.brand.yaml`.

```yaml
schema: 1
name: Acme Co                  # shown in the preview card and logs
tagline: ""                    # one sentence; not rendered by default
website: https://acme.example
handle: "@acme"
colors:
  primary: "#0E7C86"           # hook-text box, grid tiles, window accents
  accent: "#F26B21"            # highlighted caption word, numerals, end card box
  background: "#FFFFFF"        # backdrop in window styles
  text: "#111827"              # preview card text
fonts:
  heading:                     # captions (word/chunk styles), hook text, end card
    family: Poppins
    file: fonts/Poppins-800.ttf    # .ttf or .otf; libass and drawtext both need a static file
    source: Google Fonts (Poppins 800)
    license: Open font licence (Google Fonts)
    note: ""
  body:                        # karaoke captions (spotlight-lite)
    family: Inter
    file: fonts/Inter-500.ttf
logo:
  file: logo.png               # transparent PNG
  position: top-right          # top-right | top-left | bottom-right | bottom-left
  scale: 0.16                  # logo width as a fraction of video width
  show_in_videos: true
captions:
  case: as_spoken              # as_spoken | upper | lower (a style can force its own)
  highlight_color: "#F26B21"
  stroke_color: "#000000"
cta:
  text: Follow for more        # end card text when there is no keyword
  keyword: GUIDE               # end card reads DROP GUIDE BELOW (list-the-ways)
  end_card: "DROP {keyword} BELOW"
voice:
  tone: ""                     # plain words; informational
  headline_samples: []         # taken from the website
provenance: {}                 # where each color came from; written by the extractor
notes: []                      # warnings from the extractor (font substitutions, etc.)
```

Rules:

- Colors are 6-digit hex. Text on the background should reach contrast 4.5:1.
- `fonts.*.file` missing or not found: the renderer falls back to the studio's default Poppins, then to a system font. It prints a warning.
- Fonts must be static (one weight per file). The extractor pins variable Google fonts to the weight it needs.
- Never put secrets in brand.yaml.
