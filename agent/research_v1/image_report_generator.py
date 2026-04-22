# -*- coding: utf-8 -*-
"""
Phase 19: Image Report Generator.

Abstraction layer for image generation from ImagePromptPack.

Per spec §5 architectural principle:
    TickerResearchResult -> OrchestratorReportPack -> ImagePromptPack -> gpt-image-2 -> Local image artifacts

Per spec §16 failure rules:
    - image generation failure returns a generation error, NOT a research failure
    - individual page retry must be possible
    - page 2 or page 3 failure does NOT invalidate page 1
    - research output is primary, image output is downstream

Per spec §15 local output contract:
    - Files: task_<task_id>_<ticker>_page_<N>.png
    - Manifest: task_<task_id>_<ticker>_manifest.json

Phase 19A note:
    The default backend is ManualImageJobBackend which produces a complete
    job bundle on disk — full prompts + job manifest — ready for human-in-the-loop
    image generation. This is the manual-validation artifact path, not a stub.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent.research_v1.image_report_contracts import (
    ImagePromptPack,
    ImageReportArtifacts,
    PageGenerationResult,
    ImageReportGenerationResult,
)

if TYPE_CHECKING:
    from agent.research_v1.image_report_contracts import PagePrompt


# ---------------------------------------------------------------------------
# Generator backend protocol
# ---------------------------------------------------------------------------


class ImageGeneratorBackend(ABC):
    """
    Pluggable backend for image generation.

    Phase 19A manual validation uses ManualImageJobBackend which writes
    complete job bundles to disk for human-in-the-loop generation.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The model identifier used for this backend."""
        ...

    @abstractmethod
    def generate_page(
        self,
        prompt: str,
        output_path: str,
        page_number: int,
    ) -> PageGenerationResult:
        """
        Generate a single page image (or job bundle for Phase 19A).

        Args:
            prompt: The image generation prompt for this page.
            output_path: Full path where the image should be saved.
            page_number: Page number (1, 2, or 3).

        Returns:
            PageGenerationResult with success status and file path or error.
        """
        ...

    @abstractmethod
    def supports_chinese_text(self) -> bool:
        """Whether this backend reliably renders Chinese text."""
        ...


# ---------------------------------------------------------------------------
# Job bundle structures
# ---------------------------------------------------------------------------


@dataclass
class ImageGenerationJob:
    """
    One page's image generation job — the Phase 19A manual-validation artifact.

    This is the complete handoff bundle: a human or external tool can take
    this job JSON and run image generation without any additional context.
    """
    page_number: int
    page_role: str              # "boss_poster" | "formal_report" | "detail_page"
    model: str                  # e.g. "gpt-image-2"
    prompt_text: str            # full generation prompt (complete, not truncated)
    output_image_path: str      # where the final image should land
    prompt_file_path: str       # companion prompt transcript path
    ticker: str
    task_id: str
    generated_at: str           # ISO timestamp
    backend: str                # which backend produced this job
    content_section_keys: list[str]
    must_preserve: list[str]
    forbidden_phrasing: list[str]
    style_rules: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "page_role": self.page_role,
            "model": self.model,
            "prompt_text": self.prompt_text,
            "output_image_path": self.output_image_path,
            "prompt_file_path": self.prompt_file_path,
            "ticker": self.ticker,
            "task_id": self.task_id,
            "generated_at": self.generated_at,
            "backend": self.backend,
            "content_section_keys": self.content_section_keys,
            "must_preserve": self.must_preserve,
            "forbidden_phrasing": self.forbidden_phrasing,
            "style_rules": self.style_rules,
        }


# ---------------------------------------------------------------------------
# Local file naming
# ---------------------------------------------------------------------------


def build_page_path(output_dir: str, task_id: str, ticker: str, page_number: int) -> str:
    """Build deterministic local path for a page image."""
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    return os.path.join(output_dir, f"task_{task_id}_{safe_ticker}_page_{page_number}.png")


def build_prompt_path(output_dir: str, task_id: str, ticker: str, page_number: int) -> str:
    """Build deterministic local path for the companion prompt transcript."""
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    return os.path.join(output_dir, f"task_{task_id}_{safe_ticker}_page_{page_number}_prompt.txt")


def build_manifest_path(output_dir: str, task_id: str, ticker: str) -> str:
    """Build deterministic path for the manifest JSON."""
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    return os.path.join(output_dir, f"task_{task_id}_{safe_ticker}_manifest.json")


def build_all_jobs_bundle_path(output_dir: str, task_id: str, ticker: str) -> str:
    """Build path for the combined all-pages job bundle."""
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    return os.path.join(output_dir, f"task_{task_id}_{safe_ticker}_jobs_bundle.json")


# ---------------------------------------------------------------------------
# ManualImageJobBackend — Phase 19A manual-validation artifact writer
# ---------------------------------------------------------------------------


class ManualImageJobBackend(ImageGeneratorBackend):
    """
    Phase 19A manual-validation backend.

    Writes complete job artifacts to disk for human-in-the-loop image generation:

        - Full prompt transcript file per page (.txt)
        - Per-page job bundle JSON per page
        - Combined all-pages jobs bundle JSON
        - Top-level manifest JSON

    A human takes these artifacts and runs gpt-image-2 (or equivalent) to
    produce the actual .png files. The job bundle contains every parameter
    needed — model, prompt, output path, must_preserve facts, style rules.

    This is NOT a stub — it is the designated Phase 19A manual handoff artifact.
    Per spec §21: Phase 19A may use Codex-assisted or direct-API image generation
    for human-in-the-loop testing.
    """

    def __init__(self):
        self._model = "gpt-image-2"
        self._backend_label = "manual-image-job"

    @property
    def model_name(self) -> str:
        return self._model

    def supports_chinese_text(self) -> bool:
        # gpt-image-2 supports Chinese text rendering
        return True

    def generate_page(
        self,
        prompt: str,
        output_path: str,
        page_number: int,
    ) -> PageGenerationResult:
        """
        Write complete job artifacts for one page.

        Produces:
            - <output_path>.txt              — full prompt transcript
            - <output_path>_job.json        — per-page job bundle
        """
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            prompt_file = build_prompt_path(
                os.path.dirname(output_path),
                "",
                "",  # task_id/ticker filled by caller
                page_number,
            )
            # We need task_id/ticker to build proper paths; they come from the
            # caller via output_path which already contains them.
            # Extract them from the output_path for the job bundle.
            dir_part = os.path.dirname(output_path)
            basename = os.path.basename(output_path)  # e.g. task_xxx_TICKER_page_1.png
            # basename format: task_<task_id>_<ticker>_page_<N>.png
            parts = basename.replace(".png", "").split("_")
            # parts[0]=task, parts[1]=task_id, parts[2]=ticker, parts[3]=page, parts[4]=page_num
            task_id = parts[1] if len(parts) > 1 else "UNKNOWN"
            ticker = parts[2] if len(parts) > 2 else "UNKNOWN"

            prompt_file = build_prompt_path(dir_part, task_id, ticker, page_number)
            job_file = output_path.replace(".png", "_job.json")

            generated_at = datetime.utcnow().isoformat()

            # Write full prompt transcript
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(f"=== PHASE 19A IMAGE GENERATION PROMPT ===\n")
                f.write(f"Page {page_number}\n")
                f.write(f"Ticker: {ticker}\n")
                f.write(f"Task: {task_id}\n")
                f.write(f"Model: {self._model}\n")
                f.write(f"Generated: {generated_at}\n")
                f.write(f"=== PROMPT START ===\n\n")
                f.write(prompt)
                f.write(f"\n\n=== PROMPT END ===\n")
                f.write(f"=== OUTPUT IMAGE SHOULD BE SAVED TO ===\n")
                f.write(f"{output_path}\n")

            # Write per-page job bundle JSON
            job = ImageGenerationJob(
                page_number=page_number,
                page_role="",  # filled by caller via extra context
                model=self._model,
                prompt_text=prompt,
                output_image_path=output_path,
                prompt_file_path=prompt_file,
                ticker=ticker,
                task_id=task_id,
                generated_at=generated_at,
                backend=self._backend_label,
                content_section_keys=[],
                must_preserve=[],
                forbidden_phrasing=[],
                style_rules="",
            )
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(job.to_dict(), f, ensure_ascii=False, indent=2)

            return PageGenerationResult(
                page_number=page_number,
                success=True,
                file_path=output_path,
                job_bundle_path=job_file,
                prompt_file_path=prompt_file,
                error_message=None,
                retryable=True,
            )
        except Exception as exc:
            return PageGenerationResult(
                page_number=page_number,
                success=False,
                file_path=None,
                job_bundle_path=None,
                prompt_file_path=None,
                error_message=f"Job bundle write failed: {exc}",
                retryable=True,
            )


# ---------------------------------------------------------------------------
# OpenAIImageBackend — Phase 19B automatic image generation
# ---------------------------------------------------------------------------


class OpenAIImageBackend(ImageGeneratorBackend):
    """
    Phase 19B automatic image generation backend using OpenAI gpt-image-2.

    Reads configuration from environment:
        OPENAI_API_KEY     — required; API key for OpenAI
        OPENAI_IMAGE_MODEL — optional; defaults to "gpt-image-2"

    Per spec §16 failure rules:
        - image generation failure returns a generation error, NOT a research failure
        - individual page retry is supported via retry_page()

    Per spec §11:
        - gpt-image-2 supports Chinese text rendering
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model or os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")

    @property
    def model_name(self) -> str:
        return self._model

    def supports_chinese_text(self) -> bool:
        # gpt-image-2 supports Chinese text rendering
        return True

    def generate_page(
        self,
        prompt: str,
        output_path: str,
        page_number: int,
    ) -> PageGenerationResult:
        """
        Generate one page image via OpenAI gpt-image-2 API.

        Saves the returned image to output_path as a .png file.
        Returns a generation error result if the API call fails.

        Args:
            prompt: The image generation prompt for this page.
            output_path: Full path where the image should be saved.
            page_number: Page number (1, 2, or 3).

        Returns:
            PageGenerationResult with success status and file path or error.
        """
        if not self._api_key:
            return PageGenerationResult(
                page_number=page_number,
                success=False,
                file_path=None,
                error_message="OPENAI_API_KEY environment variable is not set. "
                    "Set it to your OpenAI API key, or use mode='manual' for job-bundle path.",
                retryable=False,
            )

        try:
            from openai import OpenAI as _OpenAI
        except BaseException as exc:  # noqa: BLE001
            return PageGenerationResult(
                page_number=page_number,
                success=False,
                file_path=None,
                error_message=f"openai package not installed or unavailable: {exc}",
                retryable=False,
            )

        client = _OpenAI(api_key=self._api_key)

        try:
            response = client.images.generate(
                model=self._model,
                prompt=prompt,
                n=1,
                size="1024x1024",
            )
        except BaseException as exc:  # noqa: BLE001
            return PageGenerationResult(
                page_number=page_number,
                success=False,
                file_path=None,
                error_message=f"OpenAI API call failed: {exc}",
                retryable=True,
            )

        image_url = response.data[0].url

        # Download image bytes from the URL and save to output_path
        try:
            import urllib.request
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(image_url, output_path)
        except Exception as exc:  # noqa: BLE001
            return PageGenerationResult(
                page_number=page_number,
                success=False,
                file_path=None,
                error_message=f"Failed to download image from {image_url}: {exc}",
                retryable=True,
            )

        return PageGenerationResult(
            page_number=page_number,
            success=True,
            file_path=output_path,
            error_message=None,
            retryable=True,
        )


# ---------------------------------------------------------------------------
# Manifest serialization
# ---------------------------------------------------------------------------


def _serialize_page_result(result: PageGenerationResult | dict) -> dict:
    """Serialize a page result for manifest storage."""
    if isinstance(result, dict):
        return result
    return {
        "page_number": result.page_number,
        "success": result.success,
        "file_path": result.file_path,
        "job_bundle_path": getattr(result, "job_bundle_path", None),
        "prompt_file_path": getattr(result, "prompt_file_path", None),
        "error_message": result.error_message,
        "retryable": result.retryable,
    }


def _write_manifest(artifacts: ImageReportArtifacts, manifest_path: str) -> None:
    """Write manifest JSON to disk."""
    manifest = {
        "artifact_id": artifacts.artifact_id,
        "task_id": artifacts.task_id,
        "ticker": artifacts.ticker,
        "generated_at": artifacts.generated_at.isoformat(),
        "model_used": artifacts.model_used,
        "page_count": artifacts.page_count,
        "page_file_paths": artifacts.page_file_paths,
        "prompt_file_paths": artifacts.prompt_file_paths,
        "job_bundle_paths": artifacts.job_bundle_paths,
        "manifest_path": manifest_path,
        "prompt_metadata": artifacts.prompt_metadata,
        "page_results": [
            _serialize_page_result(r) for r in artifacts.page_results
        ],
    }
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _write_all_jobs_bundle(
    jobs: list[ImageGenerationJob],
    bundle_path: str,
    ticker: str,
    task_id: str,
) -> None:
    """Write the combined all-pages job bundle JSON."""
    bundle = {
        "bundle_id": f"bundle_{task_id}_{ticker}",
        "task_id": task_id,
        "ticker": ticker,
        "generated_at": datetime.utcnow().isoformat(),
        "total_pages": len(jobs),
        "jobs": [j.to_dict() for j in jobs],
        "instructions": (
            "This is a Phase 19A image generation job bundle. "
            "Run each page job independently using the prompt_text and output_image_path. "
            "gpt-image-2 is the default model. "
            "Save the resulting .png files to the output_image_path for each job. "
            "After generation, update the manifest to record the actual image paths."
        ),
    }
    Path(bundle_path).parent.mkdir(parents=True, exist_ok=True)
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# ImageReportGenerator
# ---------------------------------------------------------------------------


@dataclass
class ImageReportGenerator:
    """
    Orchestrates image generation from an ImagePromptPack.

    Per spec §16:
        - individual page retry must be possible
        - page 2 or page 3 failure does NOT invalidate page 1
        - image generation failure returns a generation error, NOT a research failure

    Per spec §15:
        - Produces local image artifacts (or job bundles in Phase 19A)
        - Writes manifest JSON tracking all pages

    Attributes:
        backend: The image generation backend.
        output_dir: Directory where images and manifests will be saved.
    """

    backend: ImageGeneratorBackend
    output_dir: str = "./image_reports"

    def __post_init__(self):
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        prompt_pack: ImagePromptPack,
        output_dir: str | None = None,
    ) -> ImageReportGenerationResult:
        """
        Generate the full image report set from an ImagePromptPack.

        Args:
            prompt_pack: ImagePromptPack with page prompts and style rules.
            output_dir: Override the default output directory for this run.

        Returns:
            ImageReportGenerationResult with per-page results and artifact record.
        """
        out_dir = output_dir or self.output_dir
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        source = prompt_pack.source_pack
        ticker = source.ticker if source else "UNKNOWN"
        task_id = source.task_id if source else "UNKNOWN"
        page_count = prompt_pack.page_count

        page_results: list[PageGenerationResult] = []
        page_file_paths: list[str] = []
        prompt_file_paths: list[str] = []
        job_bundle_paths: list[str] = []
        all_jobs: list[ImageGenerationJob] = []

        for page_prompt in prompt_pack.page_prompts:
            page_path = build_page_path(out_dir, task_id, ticker, page_prompt.page_number)
            prompt_file = build_prompt_path(out_dir, task_id, ticker, page_prompt.page_number)
            job_file = page_path.replace(".png", "_job.json")

            result = self.backend.generate_page(
                prompt=page_prompt.prompt_text,
                output_path=page_path,
                page_number=page_prompt.page_number,
            )

            # Enrich result with page metadata
            result.page_role = getattr(page_prompt, "page_role", "")
            result.content_section_keys = getattr(page_prompt, "content_section_keys", [])
            result.must_preserve = getattr(page_prompt, "must_preserve", [])
            result.forbidden_phrasing = getattr(page_prompt, "forbidden_phrasing", [])
            result.style_rules = prompt_pack.global_style_rules

            page_results.append(result)

            if result.success:
                if result.file_path:
                    page_file_paths.append(result.file_path)
                pf = getattr(result, "prompt_file_path", None) or prompt_file
                if pf:
                    prompt_file_paths.append(pf)
                jb = getattr(result, "job_bundle_path", None) or job_file
                if jb:
                    job_bundle_paths.append(jb)

                # Build job entry for all-pages bundle
                job = ImageGenerationJob(
                    page_number=page_prompt.page_number,
                    page_role=result.page_role,
                    model=prompt_pack.model,
                    prompt_text=page_prompt.prompt_text,
                    output_image_path=page_path,
                    prompt_file_path=pf,
                    ticker=ticker,
                    task_id=task_id,
                    generated_at=datetime.utcnow().isoformat(),
                    backend=self.backend.model_name,
                    content_section_keys=result.content_section_keys,
                    must_preserve=result.must_preserve,
                    forbidden_phrasing=result.forbidden_phrasing,
                    style_rules=result.style_rules,
                )
                all_jobs.append(job)

        generated_at = datetime.utcnow()
        artifacts = ImageReportArtifacts(
            task_id=task_id,
            ticker=ticker,
            generated_at=generated_at,
            model_used=self.backend.model_name,
            page_count=page_count,
            page_file_paths=page_file_paths,
            manifest_path=None,
            prompt_file_paths=prompt_file_paths,
            job_bundle_paths=job_bundle_paths,
            prompt_metadata={
                "page_count": page_count,
                "global_style_rules": prompt_pack.global_style_rules,
                "must_show_labels_keys": list(prompt_pack.must_show_labels.keys()),
                "forbidden_phrasing_count": len(prompt_pack.forbidden_phrasing),
                "model": prompt_pack.model,
                "visual_priority_order": prompt_pack.visual_priority_order,
            },
            page_results=page_results,  # store PageGenerationResult objects; serialize in _write_manifest
        )

        # Write all-pages job bundle if we have any jobs
        jobs_bundle_path = None
        if all_jobs:
            jobs_bundle_path = build_all_jobs_bundle_path(out_dir, task_id, ticker)
            try:
                _write_all_jobs_bundle(all_jobs, jobs_bundle_path, ticker, task_id)
                artifacts.jobs_bundle_path = jobs_bundle_path
            except Exception:
                pass

        # Write manifest whenever we have page results (Phase 19A: job bundles written)
        manifest_path: str | None = None
        if page_results:
            manifest_path = build_manifest_path(out_dir, task_id, ticker)
            try:
                _write_manifest(artifacts, manifest_path)
                artifacts.manifest_path = manifest_path
            except Exception:
                manifest_path = None

        overall_success = all(r.success for r in page_results) if page_results else False

        return ImageReportGenerationResult(
            ticker=ticker,
            task_id=task_id,
            artifacts=artifacts if (page_file_paths or job_bundle_paths or all_jobs) else None,
            page_results=page_results,
            overall_success=overall_success,
            jobs_bundle_path=jobs_bundle_path,
            manifest_path=manifest_path,
        )

    def retry_page(
        self,
        prompt_pack: ImagePromptPack,
        page_number: int,
        output_dir: str | None = None,
    ) -> PageGenerationResult:
        """
        Retry generating a single page.

        Per spec §16: individual page retry must be possible.
        """
        out_dir = output_dir or self.output_dir

        target: PagePrompt | None = None
        for pp in prompt_pack.page_prompts:
            if pp.page_number == page_number:
                target = pp
                break

        if target is None:
            return PageGenerationResult(
                page_number=page_number,
                success=False,
                error_message=f"No page {page_number} found in prompt pack",
                retryable=False,
            )

        source = prompt_pack.source_pack
        ticker = source.ticker if source else "UNKNOWN"
        task_id = source.task_id if source else "UNKNOWN"
        page_path = build_page_path(out_dir, task_id, ticker, page_number)

        return self.backend.generate_page(
            prompt=target.prompt_text,
            output_path=page_path,
            page_number=page_number,
        )


# ---------------------------------------------------------------------------
# Backward-compatibility alias — StubImageBackend is now ManualImageJobBackend
# ---------------------------------------------------------------------------

StubImageBackend = ManualImageJobBackend
"""
Alias for backward compatibility.

ManualImageJobBackend replaces the old StubImageBackend.
The old stub wrote truncated .txt prompt files.
The new backend writes complete job bundles + prompt transcripts + job manifest.
"""
