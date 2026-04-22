# -*- coding: utf-8 -*-
"""
Phase 19: Image Report Pipeline - Core Contracts.

This module defines the three canonical objects that form the image-report pipeline:

    OrchestratorReportPack   — content truth produced by the orchestrator
    ImagePromptPack          — image-generation control layer
    ImageReportArtifacts    — saved output manifest

Authority split (per spec §4):
    - OrchestratorReportPack is the content authority (source: TickerResearchResult)
    - ImagePromptPack translates content into generation instructions
    - ImageReportArtifacts records what was actually generated

These objects do NOT:
    - invent or alter investment decisions
    - rewrite locked decision facts
    - introduce bearish actions
    - make the image model the decision authority
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# OrchestratorReportPack — the content truth
# ---------------------------------------------------------------------------


@dataclass
class OrchestratorReportPack:
    """
    Content truth for image report generation.

    Built after TickerResearchResult is available. The image pipeline
    consumes this and only this — it must not reach back into raw
    TickerResearchResult fields for decision facts.

    Sections (per spec §8):
        report_identity   — metadata
        decision_locked   — read-only mapped decision facts
        boss_narrative    — orchestrator-authored content blocks
        research_core     — thesis, bull/bear case, catalysts
        instrument_plan  — Phase 14-15 instrument details
        monitoring_state  — Phase 16-17 watchlist/validation state

    Rules (per spec §8):
        - decision_locked fields must NOT be creatively rewritten
        - boss_narrative may be reformatted but must stay faithful to locked facts
        - If narrative conflicts with locked facts, locked facts win
    """
    # §8.1 report_identity
    task_id: str
    ticker: str
    company_name: str
    generated_at: datetime
    language: str = "zh-CN"
    report_type: str = "boss_image_report"

    # §8.2 decision_locked — READ-ONLY mapped facts
    primary_action: str = ""
    conviction: str = "Medium"
    suggested_size: str = ""
    target_window: str = ""
    entry_reference: str | None = None
    target_reference: str | None = None
    stop_reference: str | None = None
    primary_instrument: str = ""
    validation_confidence: float | None = None
    watchlist_state: str | None = None
    alert_level: str | None = None

    # §8.3 boss_narrative — orchestrator-authored boss-readable content
    boss_summary: str = ""
    why_now: str = ""
    top_risks: str = ""
    one_line_call: str = ""

    # §8.4 research_core
    thesis_summary: str = ""
    bull_case: str = ""
    bear_case: str = ""
    catalysts: str = ""
    technical_summary: str = ""
    valuation_summary: str = ""
    must_show_numbers: list[str] = field(default_factory=list)

    # §8.5 instrument_plan
    primary_instrument_label: str = ""
    conservative_alternative: str | None = None
    alternative_instrument: str | None = None
    instrument_choice_reason: str = ""
    options_structure_summary: str = ""
    early_exit_summary: str = ""
    options_key_numbers: list[str] = field(default_factory=list)

    # §8.6 monitoring_state
    watchlist_summary: str = ""
    validation_summary: str = ""
    main_failure_mode: str = ""
    environment_fit: str = ""
    historical_support: str = ""
    regime: str = ""

    # §8.1 continued — derived after all required fields
    recommended_page_count: int = 2


# ---------------------------------------------------------------------------
# ImagePromptPack — generation control
# ---------------------------------------------------------------------------


@dataclass
class PagePrompt:
    """
    One page's generation prompt for the image model.

    Each page prompt includes:
        - page role (poster / formal / detail)
        - source content section mapping
        - hard facts to preserve
        - visual hierarchy rules
        - language rules (Chinese-first)
        - things not to invent
    """
    page_number: int            # 1, 2, or 3
    page_role: str              # "boss_poster" | "formal_report" | "detail_page"
    prompt_text: str            # full generation prompt for this page
    content_section_keys: list[str] = field(default_factory=list)  # which report sections this page uses
    must_preserve: list[str] = field(default_factory=list)        # facts that must not change
    forbidden_phrasing: list[str] = field(default_factory=list)   # phrases to avoid


@dataclass
class ImagePromptPack:
    """
    Image-generation control layer.

    Translates OrchestratorReportPack into page-specific prompts for the image model.

    Per spec §12:
        - model: defaults to "gpt-image-2"
        - page_count: 1–3, derived from report complexity
        - global_style_rules: premium executive finance, institutional tone
        - page_prompts: one PagePrompt per page
        - must_show_labels: fixed Chinese label strings
        - forbidden_phrasing: phrases the image model must not produce
        - visual_priority_order: hierarchy of what to emphasize
    """
    model: str = "gpt-image-2"
    page_count: int = 2
    global_style_rules: str = ""
    page_prompts: list[PagePrompt] = field(default_factory=list)
    must_show_labels: dict[str, str] = field(default_factory=dict)  # key -> Chinese label
    forbidden_phrasing: list[str] = field(default_factory=list)
    visual_priority_order: list[str] = field(default_factory=list)

    # Cached reference to the source pack (not serialized)
    source_pack: OrchestratorReportPack | None = None


# ---------------------------------------------------------------------------
# ImageReportArtifacts — saved output
# ---------------------------------------------------------------------------


@dataclass
class ImageReportArtifacts:
    """
    Saved output record for one ticker's image report set.

    Per spec §15:
        - task id, ticker, page count
        - local file paths for each generated page image
        - generation timestamps
        - model used
        - prompt metadata

    This object is the artifact record — actual image files live on disk
    at the paths recorded here.
    """
    task_id: str
    ticker: str
    generated_at: datetime
    model_used: str
    page_count: int
    # Image output paths (populated after image generation runs)
    page_file_paths: list[str] = field(default_factory=list)
    # Phase 19A manual-validation paths
    prompt_file_paths: list[str] = field(default_factory=list)  # full prompt transcript files
    job_bundle_paths: list[str] = field(default_factory=list)    # per-page job bundle JSONs
    jobs_bundle_path: str | None = None                        # combined all-pages bundle
    manifest_path: str | None = None
    prompt_metadata: dict[str, Any] = field(default_factory=dict)
    page_results: list[dict] = field(default_factory=list)

    # Convenience
    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def success(self) -> bool:
        """True if all pages were generated successfully."""
        if not self.page_file_paths:
            return False
        return all(bool(p) for p in self.page_file_paths)


# ---------------------------------------------------------------------------
# Generation result wrappers
# ---------------------------------------------------------------------------


@dataclass
class PageGenerationResult:
    """
    Result of generating one page (or writing one Phase 19A job bundle).

    Per spec §16 failure rules:
        - page 2 or page 3 failure does NOT invalidate page 1
        - individual page retry must be possible
        - image generation failure returns a generation error, NOT a research failure
    """
    page_number: int
    success: bool
    file_path: str | None = None          # target image path (or target .png path in Phase 19A)
    job_bundle_path: str | None = None    # per-page job bundle JSON (Phase 19A)
    prompt_file_path: str | None = None   # full prompt transcript file (Phase 19A)
    error_message: str | None = None
    retryable: bool = True
    # Page metadata (populated by generator from PagePrompt)
    page_role: str = ""
    content_section_keys: list[str] = field(default_factory=list)
    must_preserve: list[str] = field(default_factory=list)
    forbidden_phrasing: list[str] = field(default_factory=list)
    style_rules: str = ""


@dataclass
class ImageReportGenerationResult:
    """
    Full generation result for one ticker's image report set.

    Tracks per-page results so individual page failures can be retried
    without regenerating the entire set.

    Phase 19A state machine:
        - job_submitted: job bundle written to disk (prompt_ready + job_submitted)
        - artifacts_present: actual .png files exist at page_file_paths
        - overall_success: all pages have artifacts present
    """
    ticker: str
    task_id: str
    artifacts: ImageReportArtifacts | None = None
    page_results: list[PageGenerationResult] = field(default_factory=list)
    overall_success: bool = False
    # Phase 19A: combined job bundle path (written before image generation runs)
    jobs_bundle_path: str | None = None
    manifest_path: str | None = None

    @property
    def job_submitted(self) -> bool:
        """True if job bundles were written to disk (Phase 19A manual handoff ready)."""
        return self.jobs_bundle_path is not None

    @property
    def prompt_ready(self) -> bool:
        """True if prompt packs are built (pre-generation, content ready)."""
        return self.artifacts is not None

    @property
    def artifacts_present(self) -> bool:
        """
        True when actual image files exist at recorded paths.

        For a live image API backend: checks that real .png files exist at page_file_paths.
        For Phase 19A (job bundle backend): this remains False until the operator
        drops real .png files at the target paths and updates the manifest.
        In Phase 19A, job_submitted is True to indicate the bundle is ready.
        """
        if self.artifacts is None:
            return False
        # Phase 19A: job bundles written but no real PNG files yet
        if self.jobs_bundle_path:
            # Jobs bundle exists — Phase 19A is in progress, PNGs not yet generated
            return False
        return self.artifacts.success

    @property
    def failed_pages(self) -> list[int]:
        return [r.page_number for r in self.page_results if not r.success]

    @property
    def successful_pages(self) -> list[int]:
        return [r.page_number for r in self.page_results if r.success]


# ---------------------------------------------------------------------------
# Phase 19A manual validation support
# ---------------------------------------------------------------------------

MANUAL_VALIDATION_NOTICE = (
    "Phase 19A: Image generation may require manual iteration for Chinese text rendering. "
    "Image generation failure is a generation error, NOT a research failure. "
    "Research output remains valid even if image generation fails."
)


def build_default_style_rules() -> str:
    """
    Build the default global style rules per spec §14 visual direction.

    Returns:
        Multi-line style rule string for image prompt injection.
    """
    return (
        "STYLE: Premium executive finance design. Institutional tone. "
        "Chinese-first hierarchy - Chinese is the main visible label language, English is secondary support. "
        "Warm neutral background (cream, light gray, or warm white). "
        "Orange-red for action emphasis (primary decision, conviction, entry). "
        "Teal-green for positive support (targets, catalysts, upside). "
        "Restrained red for risk (stop, failure mode, bear case). "
        "Clean sans-serif typography feel. "
        "DO NOT: use marketing poster style, startup landing page, social-media infographic, "
        "crypto aesthetic, or cartoon finance style."
    )


def approved_action_labels() -> dict[str, str]:
    """
    Return the approved Chinese-first action label map per spec §10.

    Returns:
        Dict mapping English action key -> Chinese display label.
    """
    return {
        "Buy Stock": "买入股票",
        "Buy Call": "买入看涨期权",
        "Bull Call Spread": "牛市看涨价差",
        "Sell Cash-Secured Put": "卖出现金担保看跌期权",
        "Covered Call": "覆盖买入期权",
        "Watchlist": "观察名单",
        "No Trade": "不交易",
    }


def conviction_labels() -> dict[str, str]:
    """Chinese labels for conviction levels."""
    return {
        "High": "高确信",
        "Medium": "中确信",
        "Low": "低确信",
    }
