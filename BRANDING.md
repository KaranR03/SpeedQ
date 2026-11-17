# Westpac SpeedQ branding

**Merged and verified:** [PR #14](https://github.com/bharath-blazecode/Team-Astars/pull/14) delivered the SpeedQ
branding; [PR #18](https://github.com/bharath-blazecode/Team-Astars/pull/18) delivered the pale sidebar and control
refinements. Both are ancestors of remote `main` at `a184be1`, reviewed on 17 Nov 2026 (Brisbane). The live Clario
integration and its `.env` setup (#13 and #19) are also merged. Logo provenance and permission are separate below.

The team renamed Beacon Assist to **Westpac SpeedQ** and chose to retain the original dashboard partitions, sidebar
and case workflow. The current name, mark and colour system are applied across the dashboard, API reference and
retained demo pages.

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

The [published package metadata](https://cdn.jsdelivr.net/npm/@westpac/ui@1.21.0/package.json) lists MIT for the UI
package; the source paths, fill and copyright metadata were rechecked on 17 Nov 2026. A package licence does not by
itself establish permission to use a trademark or imply endorsement. The mark is included at the team's request for
this independent hackathon demonstration, with Team Astars and the non-official-service disclosure retained.

## Logo use in the dashboard and presentation

**Permission status: not verified in this repository.** No competition brand-use rule or written Westpac permission
covering the dashboard and recorded slide presentation has been supplied here. The existence of a published logo
component and the hackathon context alone do not record that permission.

Use the mark within the scope of applicable competition rules or permission from Westpac/the authorised organiser.
Check that the permission covers both the prototype and its recorded/public submission. Record the rule or permission
reference before marking this item complete. Keep the supplied mark's proportions, colours and copyright metadata,
identify Team Astars clearly and avoid claims of bank approval. If permission is unavailable, a Team Astars mark or
generic icon is an available alternative; this documentation update does not change the current dashboard asset.

This review could not retrieve Westpac's current website terms because the cloud network blocks that host. It
therefore confirms the asset's provenance, not legal clearance. See the
[website terms link in the source notes](backend/data/PROTOCOLS_SOURCES.md#the-copyright-position-read-before-adding-anything)
and the actual competition materials for the applicable conditions.

## Scope of source review

The source was read as text; its React code was not installed or executed. The saved asset contains only SVG,
metadata and path elements, without scripts, event handlers, embedded HTML, external references or remote resources.
It is served from the existing same-origin asset allowlist under the current browser security policy.

Direct access to the Westpac live website is blocked by the current cloud network policy, and no authenticated
Westpac app was available. References are the team's supplied website screenshots and the published GEL component
and its actual mark colour. This review does not cover a private bank app or internal officer dashboard. The visual
refinement and this documentation update introduce no dashboard packages, external fonts or runtime dependencies.
