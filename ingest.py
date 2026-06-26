"""Stage 1 & 2 ingestion, shared by the CLI (run_pipeline) and the API service.

Stage 1 parses the PDF into a JSONResume object; stage 2 needs that structured
object to find the GitHub profile URL. Imports are function-local so importing
this module stays side-effect free.
"""


def load_resume(pdf_path: str):
    """Parse the resume PDF into a JSONResume object (upstream PDFHandler)."""
    from pdf import PDFHandler

    return PDFHandler().extract_json_from_pdf(pdf_path)


def resume_to_text(resume) -> str:
    """Convert a JSONResume object to evidence text."""
    from transform import convert_json_resume_to_text

    return convert_json_resume_to_text(resume)


def github_to_text(resume) -> str:
    """Find the GitHub profile in the resume, fetch + classify it, to text.

    Mirrors upstream: pull profiles from resume.basics, locate the "Github"
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
