"""Fixed dashboard module identities; importing this does not run any job."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Module:
    key: str
    title: str
    command: str
    folder: str
    snapshot: str
    action: str
    help: str


MODULES = (
    Module("navidrome", "Navidrome", "report", "Navidrome", "navidrome-summary.json",
           "Generate Navidrome report [N]",
           "Read-only server collection. Manual reports bypass cooldown/resource admission. Configure config/.env privately."),
    Module("dev", "Dev", "dev-report", "Dev", "dev-last.json", "Inspect projects",
           "Configure config/projects.local.json. This action inspects Git metadata only; tests/builds require CLI dev-report --run-checks."),
    Module("audio", "Audio / FL Studio", "audio-report", "Audio", "audio-last.json", "Inventory configured folders",
           "Configure config/audio.local.json. Read-only file inventory; tag reading requires CLI audio-report --read-tags. FLP sample usage is unavailable."),
    Module("research", "Research", "research-report", "Research", "research-last.json", "Fetch research digest",
           "Configure config/research.local.json. Explicit HTTPS feed/release fetch; large repository pools rotate in bounded batches. Seen does not mean read."),
    Module("insights", "Insights", "insights-report", "Insights", "insights-summary.json", "Generate local insights [I]",
           "Reads saved history only; no network. Missing observations stay unavailable. No configuration is required."),
)
BY_KEY = {module.key: module for module in MODULES}
BY_COMMAND = {module.command: module for module in MODULES}


def event_module(event: dict) -> str:
    # Starter events without a module tag belong to the original Navidrome reporter.
    return event.get("module") or "navidrome"
