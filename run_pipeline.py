"""CLI orchestrator: resume PDF + job descriptions -> gap report + action plan.

Stages cache their JSON to <cache_dir>/<stage>.json and are skipped when the
cache file already exists (unless --no-cache is passed).
"""

import argparse
import json
from pathlib import Path
from typing import List, Optional

from match_models import RoleProfile, MatchReport, Recommendations
from pipeline.build_profile import build_profile
from pipeline.match import match
from pipeline.recommend import recommend


# ---- Stage 1 & 2 adapters (wired to real upstream code) ----
# Tests monkeypatch these. Imports are function-local so `import run_pipeline`
# and `--help` stay side-effect free.
#
# Stage 1 parses the PDF into a JSONResume object (upstream PDFHandler), which
# stage 2 needs in structured form to find the GitHub profile URL. So the
# parse step returns the JSONResume; run() converts it to text for the match
# stage and hands the same object to the GitHub adapter.


def _load_resume(pdf_path: str):
    """Parse the resume PDF into a JSONResume object (upstream PDFHandler)."""
    from pdf import PDFHandler

    return PDFHandler().extract_json_from_pdf(pdf_path)


def _load_resume_text(resume) -> str:
    """Convert a JSONResume object to evidence text."""
    from transform import convert_json_resume_to_text

    return convert_json_resume_to_text(resume)


def _load_github_text(resume) -> str:
    """Find the GitHub profile in the resume, fetch + classify it, to text.

    Mirrors score.py: pull profiles from resume.basics, locate the "Github"
    network, fetch via fetch_and_display_github_info(url). When no GitHub
    profile is present, fetch returns {} and the converter yields just the
    header, matching upstream's missing-profile behavior.
    """
    from github import fetch_and_display_github_info
    from transform import convert_github_data_to_text

    profiles = []
    if resume is not None and getattr(resume, "basics", None):
        profiles = resume.basics.profiles or []
    github_profile = next(
        (p for p in profiles if p.network and p.network.lower() == "github"),
        None,
    )
    github_data = (
        fetch_and_display_github_info(github_profile.url) if github_profile else {}
    )
    return convert_github_data_to_text(github_data)


# ---- caching helper ----


def _cached(cache_dir: Path, name: str, use_cache: bool, schema, produce):
    """Return schema instance from cache if present, else produce + persist."""
    path = cache_dir / f"{name}.json"
    if use_cache and path.exists():
        return schema.model_validate_json(path.read_text())
    obj = produce()
    path.write_text(obj.model_dump_json(indent=2))
    return obj


def run(
    pdf_path: str,
    jd_paths: List[str],
    cache_dir: str = ".pipeline_cache",
    model: Optional[str] = None,
    use_cache: bool = True,
) -> dict:
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    resume = _load_resume(pdf_path)
    if resume is None:
        raise ValueError(f"Could not parse resume PDF: {pdf_path}")
    resume_text = _load_resume_text(resume)
    github_text = _load_github_text(resume)
    job_descriptions = [Path(p).read_text() for p in jd_paths]

    profile = _cached(
        cache,
        "role_profile",
        use_cache,
        RoleProfile,
        lambda: build_profile(job_descriptions, model=model),
    )
    report = _cached(
        cache,
        "match",
        use_cache,
        MatchReport,
        lambda: match(profile, resume_text, github_text, model=model),
    )
    recs = _cached(
        cache,
        "recommendations",
        use_cache,
        Recommendations,
        lambda: recommend(report, model=model),
    )

    return {
        "role_profile": profile.model_dump(),
        "match": report.model_dump(),
        "recommendations": recs.model_dump(),
    }


def main():
    parser = argparse.ArgumentParser(description="resume-booster pipeline")
    parser.add_argument("pdf", help="path to resume PDF")
    parser.add_argument("jds", nargs="+", help="paths to job-description text files")
    parser.add_argument("--cache-dir", default=".pipeline_cache")
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    result = run(
        pdf_path=args.pdf,
        jd_paths=args.jds,
        cache_dir=args.cache_dir,
        model=args.model,
        use_cache=not args.no_cache,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
