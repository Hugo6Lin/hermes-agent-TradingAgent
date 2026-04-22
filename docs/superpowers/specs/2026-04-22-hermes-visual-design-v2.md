# Hermes Visual Design Spec v2

Date: 2026-04-22
Status: Approved design direction
Scope: Boss-facing visual system for Hermes image reports and future report surfaces

## 1. Purpose

This document defines the official visual direction for Hermes.

It exists to ensure that:

- future models do not redesign Hermes from scratch every time
- image-report prompts follow a stable visual language
- boss-facing reports look intentional, premium, and decision-first
- Hermes avoids drifting into dashboard, startup, or marketing aesthetics

This is not a business-logic spec.
It is a visual-system and page-behavior spec.

## 2. Product Identity

Hermes is not:

- a generic SaaS dashboard
- a marketing landing page
- a crypto terminal
- a PowerPoint slide deck
- a social-media infographic

Hermes is:

- a boss decision board
- an investment committee briefing
- a premium research delivery surface
- a decision-first financial presentation system

The visual system must help a boss:

1. understand the action within 3 seconds
2. understand the logic within 30 to 60 seconds
3. trust that the information is organized, deliberate, and important

## 3. Visual Personality

Hermes should feel:

- premium
- editorial
- disciplined
- warm
- decisive
- institutional

Hermes should not feel:

- playful
- noisy
- startup-generic
- over-animated
- over-minimal
- cold-terminal-like

## 4. Core Design Principle

The page must always behave like a decision surface first and an information surface second.

This means:

- one dominant zone per page
- strong hierarchy
- supporting sections visually subordinate themselves
- high information density without visual clutter

## 5. Color System

### 5.1 Core palette

- `--bg-page: #f6f1e8`
- `--bg-surface: #fbf7f0`
- `--bg-surface-muted: #f1ebe1`
- `--bg-hero: #1b1938`
- `--bg-hero-soft: #26224a`

### 5.2 Text palette

- `--text-primary: #292827`
- `--text-secondary: #5c5955`
- `--text-muted: #8b847b`
- `--text-on-dark: #e9e5dd`

### 5.3 Brand accents

- `--accent-primary: #b7a7ff`
- `--accent-secondary: #8f6fff`
- `--accent-soft: #ddd3ff`

### 5.4 Semantic colors

- `--positive: #5e9f7a`
- `--warning: #c78b42`
- `--danger: #b24f4b`
- `--info: #7a74c9`

### 5.5 Border colors

- `--border-soft: rgba(41,40,39,0.10)`
- `--border-strong: rgba(41,40,39,0.18)`
- `--border-on-dark: rgba(255,255,255,0.20)`

## 6. Color Usage Rules

### 6.1 Warm Cream background

Use warm cream tones as the default page atmosphere.

Goal:

- avoid the cold finance-terminal feeling
- create a premium paper-like base
- support long-form readability

### 6.2 Deep Purple authority

Use deep purple surfaces for high-authority, high-attention components.

Allowed use:

- hero surface
- primary decision card
- dark featured header blocks

Not allowed:

- flooding every section with dark purple
- turning the whole product into a dark-mode app

### 6.3 Lavender / Amethyst precision

Use lavender and amethyst accents for:

- decision emphasis
- section separators
- subtle hierarchy cues
- premium visual signature

Do not use them like bright startup gradients or decorative neon.

### 6.4 Risk / warning / support

- use restrained red for risk
- use soft green for positive support
- use amber for caution

These colors must feel controlled, not alarming or gamified.

## 7. Typography System

### 7.1 Display Hero

- `64px`
- weight `540`
- line-height `0.96`
- letter-spacing `0px`

Use only for:

- page-1 primary action
- high-drama decision hero statements

### 7.2 Section Header

- `34px`
- weight `500`
- line-height `1.02`

Use for:

- major page section titles

### 7.3 Card Title

- `22px`
- weight `560`
- line-height `1.15`

Use for:

- decision cards
- thesis cards
- options cards

### 7.4 Body

- `16px`
- weight `400`
- line-height `1.6`

Use for:

- paragraph content
- bullets
- research explanation

### 7.5 Meta

- `13px`
- weight `500`
- line-height `1.4`

Use for:

- labels
- annotations
- chips
- captions

## 8. Typography Rules

1. Display typography must be rare and authoritative.
2. Section headers should feel editorial, not app-like.
3. Body copy must remain readable and calm.
4. Meta text must support structure without turning into grey noise.
5. Hero typography should never be used for generic data labels.

## 9. Layout Philosophy

### Rule A: One dominant zone

Each page gets one undisputed dominant zone.

### Rule B: Supporting zones know they are secondary

Secondary content must visually step back.

### Rule C: Cards over tables

Cards are preferred over dense tables for boss-facing delivery.

### Rule D: Meaning over feature density

Do not add components just because they exist in the system.
Only surface what helps decision-making.

## 10. Component System

### 10.1 Hero card

Use for:

- primary action
- conviction
- suggested size
- target window

Visual rules:

- background: deep purple
- text: warm cream
- border: semi-transparent light border
- radius: large
- shadow: soft but present

### 10.2 Standard surface card

Use for:

- thesis
- valuation
- technical
- catalysts
- options detail

Visual rules:

- warm light surface
- strong but quiet border
- generous padding

### 10.3 Chip band

Use for:

- top risks
- validation state
- alert level
- environment / support tags

Visual rules:

- compact
- clean
- never gimmicky

### 10.4 Detail grid

Use for:

- options numbers
- early exit zones
- structured supporting detail

Visual rules:

- compact
- clean alignment
- never the visual hero

## 11. Buttons and Inputs

### 11.1 Primary button

- background: `#e9e5dd`
- text: `#292827`
- radius: `8px`

### 11.2 On dark hero surface

- background: `#e9e5dd`
- text: `#1b1938`

### 11.3 Ghost / secondary on dark

- transparent background
- border: `rgba(255,255,255,0.2)`
- text: `#e9e5dd`

### 11.4 Focus state

Default focus:

- border-color: `#292827`

On dark surfaces, optional visual enhancement may use lavender focus support if readability remains strong.

## 12. Page Architecture

### 12.1 Page 1 - Boss Poster

Purpose:

- instant decision comprehension

Required structure:

1. Hero decision block
2. Why now block
3. Top risks band
4. Instrument / validation strip

Rules:

- the action must be the biggest element
- risk chips must not compete with the hero
- no large tables
- no dense metric wall

### 12.2 Page 2 - Formal Research Page

Purpose:

- explain why the call is valid

Required structure:

1. Thesis
2. Catalysts
3. Valuation
4. Technical
5. Must-show numbers

Rules:

- more editorial than dashboard
- denser than page 1
- still card-based

### 12.3 Page 3 - Detail Page

Purpose:

- carry complexity without polluting the first two pages

Required structure:

1. Options structure
2. Early exit
3. Watchlist / validation
4. Main failure mode / monitoring

Rules:

- more structured
- slightly denser
- still within the same visual language

## 13. Content Hierarchy Rules

### 13.1 Primary action always wins

`primary_action` is always the top visual signal.

### 13.2 Why now must stay concise

`why_now` should remain bullet-oriented and fast to scan.

### 13.3 Risks appear early

`top_risks` should not be buried under long research prose.

### 13.4 Instrument choice must be selective

Only highlight:

- Primary
- Conservative
- Alternative

Do not show five equal-weight action buttons.

## 14. Anti-Rules

Do not let Hermes become:

- a Bloomberg clone
- a generic Tailwind admin
- a startup SaaS homepage
- a crypto terminal
- an over-minimal beige consulting deck
- a PPT slide export pretending to be a report

## 15. Image Report Rules

Because Hermes now uses an image-report mainline, all design guidance must work for:

- page images
- poster images
- saved and shared artifacts

This means:

- the first page must be screenshot-grade
- later pages must feel like formal research pages
- page composition must remain stable when turned into image prompts

## 16. Relationship to Prompt Building

This spec should guide:

- `OrchestratorReportPack` presentation priorities
- `ImagePromptPack` page prompt structure
- any future visual prompt builder

This spec should not:

- change business logic
- override research truth
- decide actions

## 17. Implementation Guidance

Future models implementing report visuals should:

1. read this file
2. read the image-report pipeline spec
3. respect the current action vocabulary
4. preserve decision-first hierarchy
5. avoid generic dashboard aesthetics

## 18. Final Style Sentence

Hermes should feel like:

**a premium investment committee briefing on warm paper, with deep-purple authority, lavender precision, and decision-first hierarchy.**
