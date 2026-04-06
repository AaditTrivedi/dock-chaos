"""
Dock Chaos — Chaos Engineering Toolkit for Docker Compose
==========================================================
A CLI tool that attaches to any Docker Compose environment and deliberately
injects failures to test fault tolerance and recovery behavior.
"""

import click
import asyncio
from dock_chaos.engine import ChaosEngine
from dock_chaos.reporter import ReportGenerator


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Dock Chaos — Break your Docker services on purpose."""
    pass


@cli.command()
@click.option("--project", "-p", default=None, help="Docker Compose project name (auto-detects if not specified)")
@click.option("--duration", "-d", default=60, help="Duration of chaos run in seconds (default: 60)")
@click.option("--intensity", "-i", type=click.Choice(["low", "medium", "high"]), default="medium",
              help="Chaos intensity: low (1 failure), medium (3 failures), high (continuous)")
@click.option("--target", "-t", default=None, help="Target specific service (default: random)")
@click.option("--output", "-o", default="chaos_report.md", help="Output report file path")
def attack(project, duration, intensity, target, output):
    """Run a chaos attack against your Docker Compose services."""
    click.echo(click.style("\n🔥 Dock Chaos — Starting chaos attack\n", fg="red", bold=True))

    engine = ChaosEngine(project_name=project, target_service=target)

    # Discover services
    services = engine.discover_services()
    if not services:
        click.echo(click.style("❌ No running Docker Compose services found.", fg="red"))
        click.echo("Make sure your services are running with: docker compose up")
        raise SystemExit(1)

    click.echo(f"📦 Discovered {len(services)} service(s):")
    for svc in services:
        click.echo(f"   • {svc['name']} ({svc['status']})")
    click.echo()

    # Run chaos
    click.echo(click.style(f"⚡ Running {intensity} intensity chaos for {duration}s...\n", fg="yellow"))
    results = asyncio.run(engine.run_chaos(
        duration=duration,
        intensity=intensity
    ))

    # Generate report
    reporter = ReportGenerator(results, services)
    report = reporter.generate_markdown()

    with open(output, "w") as f:
        f.write(report)

    # Print summary
    click.echo(click.style("\n📊 Chaos Report Summary\n", fg="green", bold=True))
    click.echo(reporter.generate_summary())
    click.echo(f"\nFull report saved to: {output}")


@cli.command()
@click.option("--project", "-p", default=None, help="Docker Compose project name")
def scan(project):
    """Scan and list all running Docker Compose services."""
    engine = ChaosEngine(project_name=project)
    services = engine.discover_services()

    if not services:
        click.echo("No running Docker Compose services found.")
        raise SystemExit(1)

    click.echo(click.style(f"\n📦 Found {len(services)} service(s):\n", bold=True))
    for svc in services:
        health = "✅" if svc["status"] == "running" else "❌"
        click.echo(f"  {health} {svc['name']}")
        click.echo(f"     Image: {svc['image']}")
        click.echo(f"     Status: {svc['status']}")
        click.echo(f"     Ports: {svc.get('ports', 'none')}")
        click.echo()


@cli.command()
@click.argument("report_file", default="chaos_report.md")
def show(report_file):
    """Display a previously generated chaos report."""
    try:
        with open(report_file, "r") as f:
            click.echo(f.read())
    except FileNotFoundError:
        click.echo(f"Report file '{report_file}' not found.")
        raise SystemExit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
