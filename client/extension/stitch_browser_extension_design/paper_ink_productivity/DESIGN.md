---
name: Paper & Ink Productivity
colors:
  surface: '#f4faff'
  surface-dim: '#c0dfef'
  surface-bright: '#f4faff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#e7f6ff'
  surface-container: '#daf2ff'
  surface-container-high: '#ceedfd'
  surface-container-highest: '#c9e7f8'
  on-surface: '#001f2a'
  on-surface-variant: '#40484c'
  inverse-surface: '#163441'
  inverse-on-surface: '#e0f4ff'
  outline: '#70787c'
  outline-variant: '#c0c8cc'
  surface-tint: '#2a6579'
  primary: '#16576a'
  on-primary: '#ffffff'
  primary-container: '#356f83'
  on-primary-container: '#c6eeff'
  inverse-primary: '#96cfe5'
  secondary: '#1b667c'
  on-secondary: '#ffffff'
  secondary-container: '#a5e6ff'
  on-secondary-container: '#1f697e'
  tertiary: '#714619'
  on-tertiary: '#ffffff'
  tertiary-container: '#8d5e2f'
  on-tertiary-container: '#ffe3cd'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b8eaff'
  primary-fixed-dim: '#96cfe5'
  on-primary-fixed: '#001f28'
  on-primary-fixed-variant: '#054d60'
  secondary-fixed: '#b6ebff'
  secondary-fixed-dim: '#8ed0e8'
  on-secondary-fixed: '#001f28'
  on-secondary-fixed-variant: '#004e60'
  tertiary-fixed: '#ffdcbf'
  tertiary-fixed-dim: '#f7ba83'
  on-tertiary-fixed: '#2d1600'
  on-tertiary-fixed-variant: '#663d11'
  background: '#f4faff'
  on-background: '#001f2a'
  surface-variant: '#c9e7f8'
typography:
  headline-lg:
    fontFamily: EB Garamond
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: EB Garamond
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  headline-sm:
    fontFamily: EB Garamond
    fontSize: 17px
    fontWeight: '500'
    lineHeight: 24px
  body-main:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  body-normal:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  panel-width: 400px
  edge-margin: 16px
  stack-gap: 12px
  internal-padding: 16px
  control-gap: 8px
---

## Brand & Style
The design system is centered on a "Warm Academic" aesthetic, blending the tactile reliability of physical stationery with the precision of a modern developer tool. It targets focused professionals and students who require a calm, low-friction productivity environment within a browser side panel.

The visual style is **Sophisticated Minimalism** with **Tactile / Skeuomorphic** undertones. It utilizes high-quality serif typography for hierarchy and a warm, low-blue-light color palette to reduce eye strain during long working sessions. The interface avoids aggressive "digital" whites and blacks in favor of parchment-like tones and deep ink-navy shadows.

## Colors
The default color mode is `light`, using the **Paper** palette to evoke a physical notebook. This design system provides four distinct tonal themes (Paper, Jade, Plum, Quartz) to allow for user personalization while maintaining a consistent value structure.

- **Primary & Secondary:** Used for actions and highlights. In dark mode, these merge into a single high-visibility accent.
- **Semantic Colors:** These are intentionally muted to prevent them from breaking the "warm" atmosphere of the UI.
- **Borders:** Subtle and low-contrast, acting as dividers rather than rigid containers.

## Typography
This design system employs a hybrid typographic approach. **EB Garamond** (a close alternative to Cormorant) is used for all "narrative" elements—headings, empty state titles, and section headers—to provide an authoritative, literary feel. 

**Geist** is used for all functional UI elements, data, and body text. 
- Use `16px` for primary reading content (e.g., the description inside a TaskCard).
- Use `15px` for general UI labels and secondary text.
- Use `13px` for metadata, timestamps, and utility labels.

## Layout & Spacing
The layout is optimized for a **Fixed Width** browser side panel (approx. 400px). 

- **Structure:** A single vertical column. Horizontal scrolling is strictly prohibited.
- **Margins:** 16px safe area on left and right edges.
- **Rhythm:** Elements are stacked vertically with a consistent 12px gap. 
- **Containment:** Content should be grouped into cards to maintain hierarchy in a constrained horizontal space.

## Elevation & Depth
Depth is expressed through **Ink-Tinted Ambient Shadows**. Shadows should not be neutral grey; they must use the primary text color (#23404D) at low opacities to maintain the warm aesthetic.

- **Level 1 (Cards):** Soft, multi-layered shadow. (e.g., `0 2px 4px rgba(35, 64, 77, 0.05), 0 8px 16px rgba(35, 64, 77, 0.08)`).
- **Level 2 (Active Controls/Modals):** Increased spread and blur, evoking a "lifted" paper effect.
- **Interactive Surfaces:** Elements use a subtle 1px border that is slightly darker than the surface, becoming more pronounced on hover.

## Shapes
The shape language follows a "Progressive Rounding" rule. Smaller, functional elements are sharper, while larger, structural containers are significantly softer. This creates a friendly, approachable framing for professional data. 
- Use `8px` for inputs and action buttons.
- Use `12px` for segmented controls and tab pills.
- Use `18px` for TaskCards and SuggestionCards.
- Use `26px` for any floating modals or sheet overlays.

## Components
- **Buttons:** Solid primary color for main actions. Ghost buttons (border only) for secondary actions. Rounded at 8px.
- **Tab Pills & Segmented Controls:** Uses a "floating" pill style where the active state is a physical card (Level 1 shadow) sitting atop a recessed track.
- **TaskCards:** 18px corner radius. Includes a Lucide-style checkbox (1.5px stroke). On expansion, details transition in using a vertical wipe, revealing `body-main` text.
- **SuggestionCards:** Distinguished from tasks by a subtle dashed border or a slight background tint (e.g., using the "Accent" color at 5% opacity).
- **Checkboxes & Radios:** Soft-edged (4px for checkboxes, 100% for radios). Stroke width of 1.5px to match Lucide icons.
- **Icons:** Use **Lucide** icons exclusively. Strokes are thin (1.5px) and monochromatic, using the "Text" color for consistency.
- **Input Fields:** 8px corners with the "Surface" color as the background. On focus, the border transitions to the "Primary" color with a soft 2px glow.