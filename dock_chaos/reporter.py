"""
Report Generator — Produces a fault-tolerance report card from chaos results.
"""

from datetime import datetime, timezone


class ReportGenerator:
    """Generates markdown reports and CLI summaries from chaos results."""

    def __init__(self, results: list, services: list[dict]):
        self.results = results
        self.services = services

    def generate_summary(self) -> str:
        """Generate a CLI-friendly summary."""
        total = len(self.results)
        if total == 0:
            return "No faults were injected."

        recovered = sum(1 for r in self.results if r.recovered)
        failed = total - recovered
        avg_recovery = self._avg_recovery_ms()

        lines = []
        lines.append(f"  Total faults injected:  {total}")
        lines.append(f"  Services recovered:     {recovered}/{total}")
        lines.append(f"  Services failed:        {failed}/{total}")

        if avg_recovery is not None:
            lines.append(f"  Avg recovery time:      {avg_recovery:.0f}ms")

        lines.append(f"  Fault tolerance score:  {self._score()}")
        return "\n".join(lines)

    def generate_markdown(self) -> str:
        """Generate a full markdown report."""
        lines = []
        lines.append("# Dock Chaos — Fault Tolerance Report")
        lines.append(f"\nGenerated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("")

        # Services scanned
        lines.append("## Services Scanned")
        lines.append("")
        lines.append("| Service | Image | Status |")
        lines.append("|---------|-------|--------|")
        for svc in self.services:
            lines.append(f"| {svc['name']} | {svc['image']} | {svc['status']} |")
        lines.append("")

        # Results table
        lines.append("## Fault Injection Results")
        lines.append("")
        lines.append("| # | Fault Type | Target | Recovered | Recovery Time | Error |")
        lines.append("|---|-----------|--------|-----------|---------------|-------|")
        for i, r in enumerate(self.results, 1):
            recovered_str = "✅ Yes" if r.recovered else "❌ No"
            time_str = f"{r.recovery_time_ms:.0f}ms" if r.recovery_time_ms else "—"
            error_str = r.error if r.error else "—"
            lines.append(
                f"| {i} | {r.fault_name} | {r.target} | {recovered_str} | {time_str} | {error_str} |"
            )
        lines.append("")

        # Summary
        total = len(self.results)
        recovered = sum(1 for r in self.results if r.recovered)
        avg = self._avg_recovery_ms()

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total faults injected:** {total}")
        lines.append(f"- **Recovered:** {recovered}/{total}")
        lines.append(f"- **Failed:** {total - recovered}/{total}")
        if avg is not None:
            lines.append(f"- **Average recovery time:** {avg:.0f}ms")
        lines.append(f"- **Fault tolerance score:** {self._score()}")
        lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        lines.append("")
        failed_results = [r for r in self.results if not r.recovered]
        if not failed_results:
            lines.append(
                "All services recovered from injected faults. "
                "Consider increasing chaos intensity or duration for a more rigorous test."
            )
        else:
            lines.append("The following issues were detected:\n")
            for r in failed_results:
                lines.append(f"- **{r.target}** failed to recover from `{r.fault_name}`: {r.error}")
            lines.append(
                "\nConsider adding health checks, restart policies, "
                "and graceful degradation logic to affected services."
            )

        return "\n".join(lines)

    def _avg_recovery_ms(self) -> float | None:
        """Calculate average recovery time in milliseconds."""
        times = [r.recovery_time_ms for r in self.results if r.recovery_time_ms is not None]
        if not times:
            return None
        return sum(times) / len(times)

    def _score(self) -> str:
        """Calculate a letter-grade fault tolerance score."""
        total = len(self.results)
        if total == 0:
            return "N/A"

        recovered = sum(1 for r in self.results if r.recovered)
        ratio = recovered / total
        avg = self._avg_recovery_ms()

        if ratio == 1.0 and avg is not None and avg < 500:
            return "A — Excellent"
        elif ratio == 1.0:
            return "B — Good (all recovered, but slowly)"
        elif ratio >= 0.75:
            return "C — Acceptable (some failures)"
        elif ratio >= 0.5:
            return "D — Poor (significant failures)"
        else:
            return "F — Critical (most services failed to recover)"
