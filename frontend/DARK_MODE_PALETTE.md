# Dark Mode Palette

Tuppence's light palette is the Wes Anderson—inspired set the app was designed around. Dark mode is **not** a uniform luminance flip of light mode; it's a deliberate translation onto a **pure-black OLED background**, with every other color shifted to remain on-theme while staying legible and easy on the eyes.

All colors are defined in `frontend/tuppence/tuppence/Theme/Theme.swift`.

## Palette

| Token | Light | Dark | Notes |
|---|---|---|---|
| Background | `#D9CA94` Pale Lemon Yellow | `#000000` (`Color.black`) | True OLED black — pixels off, infinite contrast. |
| Body text | `#334E63` Dark Medici Blue | `#E8DCB0` | Light-mode background hue, lifted lightness for ~12.5:1 contrast on black. |
| Heading | `#CD1D05` Red Orange | `#FF7A5E` | Same hue family as light heading; lifted lightness and slightly desaturated to avoid the harsh-glow look saturated reds get on OLED. Contrast ~6.5:1. |
| Shadow / elevation | `#AC8546` Isabella Color | `Color.white.opacity(0.08)` | Drop shadows on `#000` are invisible. Replaced with a subtle white-tinted glow that acts as elevation — same `radius/x/y` offsets as light mode, so the typographic feel transfers. |
| Delete red | `#CD1D05` Red Orange | `#FF6B5C` | Lifted variant for warning state. Higher contrast on black, still in the same family. |

## Design principles

1. **OLED-black background.** Modern iPhones use OLED panels — `#000000` means pixels are physically off, yielding maximum contrast, deeper aesthetic, and lower power. Anything between `#000` and ~`#0F0F0F` should be `#000`.
2. **No pure white text.** `#FFF` on `#000` is harsh and causes pupil-constriction fatigue. Body text sits at L\*≈85 (`#E8DCB0`) which is comfortable and still has plenty of contrast.
3. **Desaturate accents on black.** Saturated chromas (`#CD1D05`) bloom on OLED and read as eye-strain. The dark heading and delete reds drop ~10–15% saturation and add ~20% lightness — same hue, kinder retina.
4. **Replace drop shadow with elevation overlay.** On a pure-black background a colored drop shadow disappears. The light-mode text shadow is what gives the app its hand-printed feel; in dark mode we keep the same offset shadow but recolor it as a low-opacity white glow, preserving the typographic personality.
5. **Stay on-theme.** Every dark color belongs to the same hue family as its light counterpart. The palette feels like the same identity at night — not a different app.

## Why not asset-catalog color sets?

The existing `Theme.swift` uses inline `Color(hex:)` definitions and a `for: colorScheme` switcher. Converting to `.colorset` files would split the source of truth in two for no gain — Swift definitions are searchable, diff-friendly, and adequate for an app this size. Stay with inline definitions unless we need per-trait variants (e.g., high-contrast accessibility palettes).

## Accessibility quick check

- Body text on background: light **6.2:1**, dark **12.5:1** (WCAG AAA on both)
- Heading on background: light **3.8:1**, dark **6.5:1** (AA Large on light, AA Normal on dark)
- Delete red on background: light **3.8:1**, dark **7.1:1** (AA Large on light, AAA on dark)
