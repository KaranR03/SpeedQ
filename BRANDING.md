# Westpac SpeedQ branding

**Current mark:** an original customer-service headset with **one boom microphone**, drawn as a small monochrome
SVG for Team Astars. The Westpac bank logo is removed from the current source and replaced in the sidebar and
favicons. The project name, pale rose navigation and accepted dashboard partitions are retained.

**Source reviewed:** remote `main` at `3007368` on 17 Nov 2026 (Brisbane). The earlier naming/palette work (#14),
light sidebar/controls (#18), slide documentation (#20) and officer-first demo (#21) are merged. This revision
replaces the former bank mark at the team's request; historical commits retain their original snapshots.

## Palette and interaction

| Role | Colour | Use |
|---|---|---|
| Primary/action | `#DA1710` | Primary buttons, selections and active chart accents |
| Headset / action hover | `#B5120C` | Headset strokes, microphone tip and hover/high-emphasis text |
| Navigation | `#FCEDEA` | Pale rose sidebar |
| Navigation selection | `#F6DAD5` | Current item with a red inset marker |
| Navigation text | `#493735` / `#705D59` | Dark labels and supporting text |
| Panel | `#FFFFFF` | Work panels and the headset badge |
| Canvas | `#F7F7F6` | Quiet off-white background |
| Primary text | `#1F2029` | Headings and case information |
| Secondary text | `#535353` / `#636363` | Supporting labels and detail |

Colours remain defined in `frontend/styles.css`. Priority, warning and verified-state colours retain text labels.
Secondary actions use a red outline; keyboard focus is dark red on light surfaces. The team-supplied website
screenshots informed spacing, heading hierarchy and directional cues, without importing their photographs or fonts.

## Headset symbol and source

[`frontend/support-headset.svg`](frontend/support-headset.svg) is source-drawn geometry: one headband, two earpieces
and one microphone boom ending in a small capsule. It uses a single red, rounded strokes and no face or decorative
shading. The 32 × 32 view box stays sharp in a 30px sidebar icon and at favicon sizes. A 42px white badge separates it
from the pale rose sidebar.

A standard headphone emoji lacks a boom microphone and varies by platform. The SVG gives the requested support
headset the same restrained appearance across devices. It was written for this prototype without downloaded stock
emoji artwork, a third-party icon package or the former bank-logo paths. No extra dependency or font is needed.

The symbol is decorative beside the named home link, so the sidebar image has empty alternative text. The SVG also
has its own descriptive title. It contains no script, event handler, external reference or remote resource, and is
served through the existing same-origin asset allowlist. The former bank SVG is removed from that allowlist and its
old asset URL returns 404. A new favicon URL avoids retaining the old mark through the previous asset address.

## Logo use in the dashboard and presentation

Use the original headset symbol and fresh prototype screenshots for the slide presentation. Replace any bank logo
still present in the externally maintained deck before export; that external deck is not edited by this repository
change. The [slide plan](docs/video/SHOT_LIST.md) and [narration script](docs/video/SCRIPT.md) describe the production work.

The **Westpac SpeedQ** project name remains at the team's request, alongside Team Astars and the independent
hackathon-prototype/synthetic-data disclosures. Removing the bank artwork is not a claim of official approval or a
blanket clearance for other materials. Follow the applicable competition guidance for the project name and other
content; the [source notes](backend/data/PROTOCOLS_SOURCES.md) record separate content-review work.
