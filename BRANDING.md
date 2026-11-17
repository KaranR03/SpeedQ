# Westpac SpeedQ branding

**Merged and verified:** [PR #14](https://github.com/bharath-blazecode/Team-Astars/pull/14) merged commit `d057af0`
into `main` at `60adbde`. Its ancestry in the later `main` at `37091a8` was checked on 17 Nov 2026 (Brisbane),
including the teammate's merged live Clario integration. This revision retains that integration.

The team renamed Beacon Assist to **Westpac SpeedQ** and chose to retain the original dashboard partitions, sidebar
and case workflow. The later horizontal-navigation concept was not selected. This update changes the name, mark and
colour system across the current dashboard, API reference and retained demo pages.

## Palette and interaction

| Role | Colour | Use |
|---|---|---|
| Brand/action | `#DA1710` | Primary buttons, current selections, active chart accents |
| Action hover | `#B5120C` | Hover and high-emphasis red text |
| Navigation | `#FCEDEA` | Pale rose sidebar, retaining the selected layout |
| Navigation selection | `#F6DAD5` | Current sidebar item, with a red inset marker |
| Navigation text | `#493735` / `#705D59` | Dark labels and supporting copy on the light sidebar |
| Panel | `#FFFFFF` | Existing work panels |
| Canvas | `#F7F7F6` | Quiet off-white background |
| Primary text | `#1F2029` | High-contrast headings and case information |
| Secondary text | `#535353` / `#636363` | Labels and supporting detail |

Colours are centrally defined in `frontend/styles.css` and used by insights and live intake. Functional priority,
warning and verified-state colours remain distinct and text-labelled. Primary buttons have red hover/pressed states;
secondary buttons use the red outline seen in the supplied reference screenshots. Keyboard focus is a dark red on
both the light sidebar and work surfaces. Layout and decision semantics are retained.

## Refinements from the team's reference images

This revision uses the Westpac help and corporate website screenshots supplied by the team. Their useful patterns
are white/soft-grey surfaces, clear heading weight, consistent card gutters, red outlined secondary actions and red
directional cues. These are adapted to the existing officer dashboard, without adding a marketing hero, decorative
photography, oversized display headings or website footer columns to the work area.

The former deep-red sidebar is replaced by pale rose with dark text, a richer rose active row and a red inset
selection marker. The demo toolbar follows the same light treatment. Queue and preview gutters align at 24px on
wide screens; existing compact/mobile overrides remain. Table headings and section labels are easier to scan, and
the existing case-opening chevron uses the action red. The four customer detail fields use a balanced two-column
grid, including the mobile field added by the Clario integration. The supplied screenshots themselves are not committed or
embedded as product assets; no additional images, fonts, packages or runtime requests are introduced.

## Westpac mark provenance

`frontend/westpac-mark.svg` contains the three static paths from the published `WBCLogo` component in
[`@westpac/ui` version 1.21.0](https://www.npmjs.com/package/@westpac/ui/v/1.21.0), distributed by Westpac GEL.
The reviewed source is
[wbc-logo.js](https://cdn.jsdelivr.net/npm/@westpac/ui@1.21.0/dist/components/symbol/components/logos/wbc-logo.js),
with copyright metadata supplied by
[symbol.component.js](https://cdn.jsdelivr.net/npm/@westpac/ui@1.21.0/dist/components/symbol/symbol.component.js).
The published paths, proportions, `#DA1710` fill and “Copyright © 2025 by Westpac Banking Corporation. All rights
reserved.” notice are retained. A local white surround keeps the red mark readable within the light rose sidebar.

The published package metadata declares MIT for the UI package; that does not establish permission to represent
Westpac or confer rights to its trademarks. The mark is included at the team's explicit request for this independent
hackathon demonstration. The dashboard continues to identify Team Astars and states that it is not an official
Westpac service. Competition brand-use and content guidance still apply.

## Scope of source review

The source was read as text; its React code was not installed or executed. The saved asset contains only SVG,
metadata and path elements, without scripts, event handlers, embedded HTML, external references or remote resources.
It is served from the existing same-origin asset allowlist under the current browser security policy.

Direct access to the Westpac live website is blocked by the current cloud network policy, and no authenticated
Westpac app was available. References are the team's supplied website screenshots and the published GEL component
and its actual mark colour; this is not a
claim to have reviewed a current private bank app or internal officer dashboard. No additional dashboard packages,
external fonts or runtime dependencies were introduced.
