# -*- coding: utf-8 -*-
"""
Phase 19: Image Report Service.

Service layer that chains the full image-report pipeline:

    TickerResearchResult
        -> OrchestratorReportPack (orchestrator_reporting)
        -> ImagePromptPack (image_prompt_builder)
        -> image artifacts (image_report_generator)

Per spec §5 architectural principle and §6 product surfaces:
    - Primary surface: image report set (poster + report pages)
    - Page 1: Boss decision poster
    - Page 2: Formal research summary page
    - Page 3: Optional detail page

Per spec §16 failure rules:
    - image generation failure must not invalidate research results
    - research output is primary, image output is downstream
    - image generation failure returns a generation error, NOT a research failure

Phase 19A state machine:
    1. prompt_ready     — ImagePromptPack built, content truth established
    2. job_submitted   — job bundles written to disk, ready for manual generation
    3. artifacts_present — actual .png image files exist at recorded paths

The service does NOT:
    - make the image model the decision authority
    - wire full API billing automation (Phase 19A manual path)
    - alter the research pipeline
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from agent.research_v1.image_report_contracts import (
    OrchestratorReportPack,
    ImagePromptPack,
    ImageReportArtifacts,
    ImageReportGenerationResult,
    MANUAL_VALIDATION_NOTICE,
)
from agent.research_v1.orchestrator_reporting import build_report_pack
from agent.research_v1.image_prompt_builder import build_prompt_pack
from agent.research_v1.image_report_generator import (
    ImageReportGenerator,
    ImageGeneratorBackend,
    ManualImageJobBackend,
    OpenAIImageBackend,
    ImageGenerationJob,
)

if TYPE_CHECKING:
    from agent.research_v1.app import TickerResearchResult


# ---------------------------------------------------------------------------
# Service result
# ---------------------------------------------------------------------------


@dataclass
class ImageReportServiceResult:
    """
    Full image-report service result.

    Contains the derived content (pack, prompt_pack) and generation result.
    The content objects remain valid even if image generation fails — per spec §16,
    image generation failure is a generation error, NOT a research failure.

    Phase 19A state machine properties:
        - prompt_ready:     ImagePromptPack is built and ready
        - job_submitted:   job bundles are on disk, ready for manual image generation
        - artifacts_present: actual .png image files exist at recorded paths
    """
    ticker: str
    task_id: str
    report_pack: OrchestratorReportPack
    prompt_pack: ImagePromptPack
    generation_result: ImageReportGenerationResult | None
    manual_validation_notice: str = MANUAL_VALIDATION_NOTICE

    @property
    def prompt_ready(self) -> bool:
        """True when ImagePromptPack is built and ready (pre-generation)."""
        return self.prompt_pack is not None and len(self.prompt_pack.page_prompts) > 0

    @property
    def job_submitted(self) -> bool:
        """
        True when job bundles are written to disk.

        Phase 19A: the operator can now take the job bundle files and run
        image generation manually or via an external tool.
        """
        if self.generation_result is None:
            return False
        return bool(self.generation_result.jobs_bundle_path)

    @property
    def artifacts_present(self) -> bool:
        """True when actual image files exist at recorded paths."""
        if self.generation_result is None:
            return False
        return self.generation_result.artifacts_present

    @property
    def overall_success(self) -> bool:
        """True if all pages generated successfully."""
        if self.generation_result is None:
            return False
        return self.generation_result.overall_success

    @property
    def success(self) -> bool:
        """Alias for overall_success for backward compatibility."""
        return self.overall_success

    @property
    def artifacts(self) -> ImageReportArtifacts | None:
        if self.generation_result is None:
            return None
        return self.generation_result.artifacts

    @property
    def failed_pages(self) -> list[int]:
        if self.generation_result is None:
            return []
        return self.generation_result.failed_pages

    @property
    def job_bundle_path(self) -> str | None:
        """Path to the combined all-pages job bundle (Phase 19A handoff artifact)."""
        if self.generation_result is None:
            return None
        return self.generation_result.jobs_bundle_path

    @property
    def manifest_path(self) -> str | None:
        """Path to the manifest JSON."""
        if self.generation_result is None:
            return None
        # Check direct path first
        if self.generation_result.manifest_path:
            return self.generation_result.manifest_path
        # Fall back to artifacts-level manifest path
        if (
            self.generation_result.artifacts
            and self.generation_result.artifacts.manifest_path
        ):
            return self.generation_result.artifacts.manifest_path
        return None

    @property
    def research_valid(self) -> bool:
        """
        Research validity is independent of image generation success.

        Per spec §16: image generation failure does NOT invalidate research.
        """
        return True

    @property
    def phase_19a_job_state(self) -> str:
        """
        Human-readable Phase 19A job state.

        Returns one of:
            - "not_started"      : no generation attempted
            - "content_ready"    : prompt pack built, not yet submitted
            - "job_submitted"   : job bundles on disk, awaiting image generation
            - "partial"          : some pages succeeded, some failed
            - "artifacts_present": actual image files generated
        """
        if self.generation_result is None:
            return "not_started"
        if self.artifacts_present:
            return "artifacts_present"
        if self.job_submitted:
            return "partial" if self.failed_pages else "job_submitted"
        if self.prompt_ready:
            return "content_ready"
        return "not_started"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ImageReportService:
    """
    Orchestrates the full image-report pipeline from TickerResearchResult.

    Pipeline (per spec §5):
        TickerResearchResult
            -> build_report_pack() [OrchestratorReportPack]
            -> build_prompt_pack() [ImagePromptPack]
            -> ImageReportGenerator [image artifacts]

    Phase 19A default backend is ManualImageJobBackend which writes complete
    job bundles to disk. The operator runs gpt-image-2 manually and drops the
    resulting .png files at the recorded paths, then the manifest is complete.
    """

    def __init__(
        self,
        backend: ImageGeneratorBackend | None = None,
        output_dir: str = "./image_reports",
        mode: str = "manual",
    ):
        """
        Initialize the image report service.

        Args:
            backend: Explicit backend instance. If provided, takes precedence over mode.
            output_dir: Default output directory for generated files.
            mode: Generation mode — "manual" (default, job bundles) or "openai" (live API).
                Ignored if backend is explicitly provided.
        """
        self._output_dir = output_dir
        if backend is not None:
            self._backend = backend
        elif mode == "openai":
            self._backend = OpenAIImageBackend()
        else:
            self._backend = ManualImageJobBackend()
        self._generator = ImageReportGenerator(
            backend=self._backend,
            output_dir=output_dir,
        )

    def run(
        self,
        research_result: "TickerResearchResult",
        company_name: str = "",
        output_dir: str | None = None,
        mode: str = "manual",
    ) -> ImageReportServiceResult:
        """
        Run the full image-report pipeline on a TickerResearchResult.

        Args:
            research_result: Result from the Hermes research pipeline.
            company_name: Optional company name for display labels.
            output_dir: Override the default output directory.
            mode: Generation mode — "manual" (default, job bundles) or "openai" (live API).
                When "openai", uses OpenAI gpt-image-2 to generate real .png images.
                When "manual", writes job bundles to disk for human-in-the-loop generation.

        Returns:
            ImageReportServiceResult with content packs and generation result.

        Phase 19A / 19B output:
            - Manual: job bundles written to output_dir, manifest JSON written,
              operator runs gpt-image-2 manually, drops .png files at page_file_paths
            - OpenAI: real .png images generated via OpenAI API, manifest updated
        """
        ticker = research_result.ticker
        task_id = research_result.task.task_id
        out_dir = output_dir or self._output_dir

        # Step 1: Build content truth
        report_pack = build_report_pack(research_result, company_name=company_name)

        # Step 2: Build generation control layer
        prompt_pack = build_prompt_pack(report_pack)

        # Step 3: Select backend based on mode and explicit-backend precedence
        # Explicit backend set in __init__ is NOT overridden by mode.
        # mode="openai" creates a new OpenAIImageBackend() (ignores explicit backend).
        if mode == "openai":
            backend = OpenAIImageBackend()
        else:
            backend = self._backend  # use whatever was set in __init__

        generator = ImageReportGenerator(backend=backend, output_dir=out_dir)

        # Step 4: Generate images / job bundles
        generation_result = generator.generate(
            prompt_pack=prompt_pack,
            output_dir=out_dir,
        )

        return ImageReportServiceResult(
            ticker=ticker,
            task_id=task_id,
            report_pack=report_pack,
            prompt_pack=prompt_pack,
            generation_result=generation_result,
        )

    def retry_page(
        self,
        service_result: ImageReportServiceResult,
        page_number: int,
        output_dir: str | None = None,
    ) -> ImageReportServiceResult:
        """
        Retry generating a specific page.

        Per spec §16: individual page retry must be possible.
        """
        gen_result = service_result.generation_result
        if gen_result is None:
            raise ValueError("No generation result to retry")

        page_result = self._generator.retry_page(
            prompt_pack=service_result.prompt_pack,
            page_number=page_number,
            output_dir=output_dir,
        )

        # Rebuild page results list with the retried page
        new_page_results = []
        for existing in gen_result.page_results:
            if existing.page_number == page_number:
                new_page_results.append(page_result)
            else:
                new_page_results.append(existing)

        # Reconcile file path lists (filter out None values)
        new_file_paths: list[str] = [
            str(r.file_path) for r in new_page_results
            if r.success and r.file_path
        ]
        new_prompt_paths: list[str] = [
            str(getattr(r, "prompt_file_path", "") or "")
            for r in new_page_results
            if r.success and getattr(r, "prompt_file_path", None)
        ]
        new_job_paths: list[str] = [
            str(getattr(r, "job_bundle_path", "") or "")
            for r in new_page_results
            if r.success and getattr(r, "job_bundle_path", None)
        ]

        out_dir = output_dir or self._output_dir

        # Rebuild all_jobs from current page results
        all_jobs: list[ImageGenerationJob] = []
        model_used = "gpt-image-2"
        if gen_result.artifacts:
            model_used = gen_result.artifacts.model_used

        for r in new_page_results:
            if r.success:
                job = ImageGenerationJob(
                    page_number=r.page_number,
                    page_role=getattr(r, "page_role", ""),
                    model=model_used,
                    prompt_text=getattr(r, "prompt_text", "")
                    if hasattr(r, "prompt_text") else "",
                    output_image_path=str(r.file_path) if r.file_path else "",
                    prompt_file_path=str(getattr(r, "prompt_file_path", "") or ""),
                    ticker=service_result.ticker,
                    task_id=service_result.task_id,
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    backend="manual-image-job",
                    content_section_keys=list(getattr(r, "content_section_keys", [])),
                    must_preserve=list(getattr(r, "must_preserve", [])),
                    forbidden_phrasing=list(getattr(r, "forbidden_phrasing", [])),
                    style_rules=getattr(r, "style_rules", ""),
                )
                all_jobs.append(job)

        # Write all-pages job bundle
        jobs_bundle_path: str | None = None
        if all_jobs:
            jobs_bundle_path = f"task_{service_result.task_id}_{service_result.ticker}_jobs_bundle.json"
            from agent.research_v1.image_report_generator import (
                _write_all_jobs_bundle,
                build_all_jobs_bundle_path,
            )
            bundle_path = build_all_jobs_bundle_path(
                out_dir, service_result.task_id, service_result.ticker
            )
            try:
                _write_all_jobs_bundle(all_jobs, bundle_path, service_result.ticker, service_result.task_id)
                jobs_bundle_path = bundle_path
            except Exception:
                jobs_bundle_path = None

        # Rebuild artifacts
        old_artifacts = gen_result.artifacts
        new_artifacts: ImageReportArtifacts | None = None
        if old_artifacts:
            new_artifacts = ImageReportArtifacts(
                task_id=service_result.task_id,
                ticker=service_result.ticker,
                generated_at=old_artifacts.generated_at,
                model_used=old_artifacts.model_used,
                page_count=old_artifacts.page_count,
                page_file_paths=new_file_paths,
                prompt_file_paths=new_prompt_paths,
                job_bundle_paths=new_job_paths,
                jobs_bundle_path=jobs_bundle_path,
                manifest_path=None,
                prompt_metadata=old_artifacts.prompt_metadata,
                page_results=[
                    {
                        "page_number": r.page_number,
                        "success": r.success,
                        "file_path": r.file_path,
                        "job_bundle_path": getattr(r, "job_bundle_path", None),
                        "prompt_file_path": getattr(r, "prompt_file_path", None),
                        "error_message": r.error_message,
                        "retryable": r.retryable,
                    }
                    for r in new_page_results
                ],
            )

        # Write manifest
        manifest_path: str | None = None
        if new_artifacts and new_job_paths:
            from agent.research_v1.image_report_generator import (
                _write_manifest,
                build_manifest_path,
            )
            manifest_path = build_manifest_path(out_dir, service_result.task_id, service_result.ticker)
            try:
                _write_manifest(new_artifacts, manifest_path)
                if new_artifacts:
                    new_artifacts.manifest_path = manifest_path
            except Exception:
                manifest_path = None

        new_gen_result = ImageReportGenerationResult(
            ticker=service_result.ticker,
            task_id=service_result.task_id,
            artifacts=new_artifacts,
            page_results=new_page_results,
            overall_success=all(r.success for r in new_page_results),
            jobs_bundle_path=jobs_bundle_path,
            manifest_path=manifest_path,
        )

        return ImageReportServiceResult(
            ticker=service_result.ticker,
            task_id=service_result.task_id,
            report_pack=service_result.report_pack,
            prompt_pack=service_result.prompt_pack,
            generation_result=new_gen_result,
        )

    @property
    def output_dir(self) -> str:
        """Default output directory for generated images and job bundles."""
        return self._output_dir

    def set_backend(self, backend: ImageGeneratorBackend) -> None:
        """Swap the image generation backend (e.g., for switching from manual to live API)."""
        self._backend = backend
        self._generator = ImageReportGenerator(
            backend=backend,
            output_dir=self._output_dir,
        )
