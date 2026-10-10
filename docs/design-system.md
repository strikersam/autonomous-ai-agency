# Design system

The dashboard (`frontend/src`) and the public landing page (`frontend/public/home.html`)
share one visual language. Tokens live in `frontend/src/index.css`; the landing page
carries a copy of the same values in its own `<style>` block because it ships without
the app bundle.

## Principles

- **Plain language first.** Screens say what is happening and what needs the reader,
  in sentences a non-technical owner understands. Technical detail is one click away
  (Home's "System details", Settings), never in the way.
- **One accent.** Ink blue marks the primary action, the current selection and focus.
  Green, amber and red are reserved for state (working, needs attention, failed) and
  always come with a word or icon, never colour alone.
- **Calm surfaces.** No glows, aurora, glass or tilt. Depth is a 1px border and a soft,
  offset shadow. Cards are not nested inside cards; lists use dividers.
- **Light and dark.** Light is the default, dark follows the OS, and the sidebar's
  Auto / Light / Dark switch overrides it (`src/theme.js`, stored under `theme`).

## Tokens

| Token | Use |
|-------|-----|
| `--bg-base`, `--bg-sidebar`, `--bg-surface`, `--bg-elevated` | Page, navigation, panels, popovers |
| `--text-primary` … `--text-muted` | Four text steps; muted still passes 4.5:1 on every ground |
| `--border`, `--border-soft`, `--border-strong` | Hairlines |
| `--accent`, `--accent-hover`, `--accent-soft`, `--on-accent` | The one accent and text on it |
| `--success`, `--warning`, `--danger`, `--violet` | State and data series |
| `--ink`, `--shade` | Bases for translucent tints and shadows: `color-mix(in oklab, var(--ink) 6%, transparent)` |
| `--radius-xs` 6 · `--radius-sm` 8 · `--radius` 12 · `--radius-lg` 16 | Tighter inside, softer outside |

Never write a raw hex or `rgba()` in a component: it will be wrong in one of the two
themes. Use a token, or `color-mix()` against one.

## Type

- Interface: **Instrument Sans**, 15–17px body, 13px minimum for secondary text.
- Code, logs and identifiers only: **JetBrains Mono**. Numbers elsewhere use
  `font-variant-numeric: tabular-nums`.
- Headings are sentence case. No eyebrow/kicker labels above headings and no
  uppercase letter-spaced labels.

## Components

- **Shell** (`v5/AppShell.jsx`): sidebar on desktop, header + bottom bar + drawer on
  mobile, skip link, `<main id="main-content">`, `aria-current` on the active item.
- **HubTabs** (`v5/components/ui/HubTabs.jsx`): WAI-ARIA tablist with arrow keys;
  scrolls sideways on phones.
- **Glyph** (`v5/components/ui/Glyph.jsx`): maps legacy emoji icon strings to the
  stroke icon set. New code imports icons directly.
- **ErrorBoundary**: wraps every hub tab, so one failing view never blanks the app.
- **StatusPill**, **Spinner**, `.skeleton`, `.app-button-primary|secondary|ghost`.

## Accessibility checklist

Visible focus ring on every control, 44px touch targets on coarse pointers, labels on
every input, `aria-label` on icon-only buttons, reduced-motion respected, no
horizontal page scroll at 390px.
