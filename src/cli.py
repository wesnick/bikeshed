import asyncio
import click
import os
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from typing import List, Optional

from src.service.pulse_mcp_api import PulseMCPAPI, MCPServer
from src.dependencies import get_db
# from src.fixtures import (
#     create_flow_template, create_flow, create_session,
#     create_message, create_artifact, create_scratchpad,
#     create_conversation, create_complete_flow_session
# )

console = Console()

@click.command()
def hello():
    click.echo('Hello World!')

@click.command()
@click.argument('query', required=False)
@click.option('--limit', default=20, help='Maximum number of results to display')
def search_mcp(query: Optional[str], limit: int):
    """Search for MCP servers and display results interactively."""
    asyncio.run(_search_mcp(query, limit))

async def _search_mcp(query: Optional[str], limit: int):
    api = PulseMCPAPI()

    if not query:
        query = Prompt.ask("Enter search query", default="")

    with console.status(f"Searching for MCP servers matching '{query}'..."):
        try:
            response = await api.get_servers(query=query, count_per_page=limit)
            servers = response.servers
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            return

    if not servers:
        console.print(f"No servers found matching '{query}'")
        return

    current_page = 0
    page_size = 10
    total_pages = (len(servers) + page_size - 1) // page_size

    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(servers))
        page_servers = servers[start_idx:end_idx]

        table = Table(title=f"MCP Servers ({len(servers)} results)")
        table.add_column("#", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Description", style="yellow")
        table.add_column("GitHub Stars", justify="right")

        for i, server in enumerate(page_servers, start=start_idx + 1):
            table.add_row(
                str(i),
                server.name,
                server.short_description or "No description",
                f"⭐ {server.github_stars}" if server.github_stars else "N/A"
            )

        console.print(table)
        console.print(f"Page {current_page + 1}/{total_pages}")
        console.print("\n[bold]Commands:[/bold]")
        console.print("  [cyan]number[/cyan]: View server details")
        if total_pages > 1:
            console.print("  [cyan]n[/cyan]: Next page" if current_page < total_pages - 1 else "", end="")
            console.print("  [cyan]p[/cyan]: Previous page" if current_page > 0 else "")
        console.print("  [cyan]q[/cyan]: Quit")

        choice = Prompt.ask("Enter command")

        if choice.lower() == 'q':
            break
        elif choice.lower() == 'n' and current_page < total_pages - 1:
            current_page += 1
        elif choice.lower() == 'p' and current_page > 0:
            current_page -= 1
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(servers):
                display_server_details(servers[idx])
                input("\nPress Enter to return to the list...")
            else:
                console.print("[bold red]Invalid server number[/bold red]")
                input("\nPress Enter to continue...")

def display_server_details(server: MCPServer):
    """Display detailed information about a server."""
    os.system('clear' if os.name == 'posix' else 'cls')

    # Create a panel with server details
    details = []
    details.append(f"[bold cyan]Name:[/bold cyan] {server.name}")

    if server.url:
        details.append(f"[bold cyan]URL:[/bold cyan] {server.url}")

    if server.external_url:
        details.append(f"[bold cyan]External URL:[/bold cyan] {server.external_url}")

    if server.short_description:
        details.append(f"[bold cyan]Description:[/bold cyan] {server.short_description}")

    if server.source_code_url:
        details.append(f"[bold cyan]Source Code:[/bold cyan] {server.source_code_url}")

    if server.github_stars is not None:
        details.append(f"[bold cyan]GitHub Stars:[/bold cyan] ⭐ {server.github_stars}")

    if server.package_registry:
        details.append(f"[bold cyan]Package Registry:[/bold cyan] {server.package_registry}")

    if server.package_name:
        details.append(f"[bold cyan]Package Name:[/bold cyan] {server.package_name}")

    if server.package_download_count is not None:
        details.append(f"[bold cyan]Package Downloads:[/bold cyan] {server.package_download_count}")

    if server.EXPERIMENTAL_ai_generated_description:
        details.append(f"[bold cyan]AI Description:[/bold cyan] {server.EXPERIMENTAL_ai_generated_description}")

    panel = Panel("\n".join(details), title=f"Server Details: {server.name}", expand=False)
    console.print(panel)

# @click.command()
# @click.option('--templates', default=2, help='Number of flow templates to create')
# @click.option('--flows', default=3, help='Number of flows to create')
# @click.option('--sessions', default=5, help='Number of sessions to create')
# @click.option('--messages-per-session', default=5, help='Number of messages per session')
# @click.option('--artifacts', default=10, help='Number of artifacts to create')
# @click.option('--scratchpads', default=2, help='Number of scratchpads to create')
# @click.option('--complete-flows', default=1, help='Number of complete flows with all related entities')
# def create_fixtures(templates, flows, sessions, messages_per_session, artifacts, scratchpads, complete_flows):
#     """Create database fixtures for development and testing."""
#     asyncio.run(_create_fixtures(
#         templates, flows, sessions, messages_per_session,
#         artifacts, scratchpads, complete_flows
#     ))
#
# async def _create_fixtures(templates, flows, sessions, messages_per_session, artifacts, scratchpads, complete_flows):
#     """Async implementation of fixture creation."""
#     db_generator = get_db()
#     db_session = await anext(db_generator)
#     try:
#         with console.status("[bold green]Creating fixtures...") as status:
#             # Create templates
#             status.update("[bold green]Creating flow templates...")
#             created_templates = []
#             for i in range(templates):
#                 template = await create_flow_template(db_session, name=f"Template {i+1}")
#                 created_templates.append(template)
#
#             # Create flows
#             status.update("[bold green]Creating flows...")
#             created_flows = []
#             for i in range(flows):
#                 # Assign some flows to templates
#                 template = created_templates[i % len(created_templates)] if created_templates else None
#                 flow = await create_flow(
#                     db_session,
#                     template=template,
#                     name=f"Flow {i+1}",
#                     strategy=["sequential", "parallel", "adaptive"][i % 3]
#                 )
#                 created_flows.append(flow)
#
#             # Create sessions
#             status.update("[bold green]Creating sessions...")
#             created_sessions = []
#             for i in range(sessions):
#                 # Assign some sessions to flows
#                 flow = created_flows[i % len(created_flows)] if created_flows else None
#                 template = created_templates[i % len(created_templates)] if created_templates else None
#                 session_obj = await create_session(
#                     db_session,
#                     flow=flow,
#                     template=template,
#                     summary=f"Session {i+1} summary"
#                 )
#                 created_sessions.append(session_obj)
#
#             # Create conversations (messages)
#             status.update("[bold green]Creating messages...")
#             for session_obj in created_sessions:
#                 await create_conversation(
#                     db_session,
#                     num_messages=messages_per_session,
#                     session_obj=session_obj
#                 )
#
#             # Create artifacts
#             status.update("[bold green]Creating artifacts...")
#             for i in range(artifacts):
#                 # Distribute artifacts among sessions, flows, etc.
#                 source_type = ["message", "session", "flow"][i % 3]
#                 if source_type == "session" and created_sessions:
#                     await create_artifact(
#                         db_session,
#                         name=f"Artifact {i+1}",
#                         source_session=created_sessions[i % len(created_sessions)]
#                     )
#                 elif source_type == "flow" and created_flows:
#                     await create_artifact(
#                         db_session,
#                         name=f"Artifact {i+1}",
#                         source_flow=created_flows[i % len(created_flows)]
#                     )
#                 else:
#                     await create_artifact(db_session, name=f"Artifact {i+1}")
#
#             # Create scratchpads
#             status.update("[bold green]Creating scratchpads...")
#             for i in range(scratchpads):
#                 await create_scratchpad(
#                     db_session,
#                     name=f"Scratchpad {i+1}",
#                     description=f"Notes and ideas for project {i+1}"
#                 )
#
#             # Create complete flows
#             status.update("[bold green]Creating complete flows...")
#             for i in range(complete_flows):
#                 await create_complete_flow_session(
#                     db_session,
#                     num_messages=messages_per_session,
#                     num_artifacts=3
#                 )
#
#             await db_session.commit()
#
#         console.print(f"[bold green]✓[/bold green] Successfully created fixtures:")
#         console.print(f"  • {templates} flow templates")
#         console.print(f"  • {flows} flows")
#         console.print(f"  • {sessions} sessions with {messages_per_session} messages each")
#         console.print(f"  • {artifacts} artifacts")
#         console.print(f"  • {scratchpads} scratchpads")
#         console.print(f"  • {complete_flows} complete flows with all related entities")
#
#     except Exception as e:
#         await db_session.rollback()
#         console.print(f"[bold red]Error creating fixtures:[/bold red] {str(e)}")
#         raise
#     finally:
#         # Close the database session
#         await db_generator.aclose()

@click.command()
@click.option('--modules', '-m', multiple=True, default=['src.types'],
              help='Module names to load schemas from (can be used multiple times)')
@click.option('--scan-all/--decorated-only', default=False,
              help='Scan all BaseModel classes or only those with @register_schema decorator')
def load_schemas(modules, scan_all):
    """Load schemas from specified modules into the registry."""
    from src.core.registry import Registry
    from src.core.config_loader import SchemaLoader

    registry = Registry()
    loader = SchemaLoader(registry)

    total_schemas = loader.load_from_modules(list(modules), scan_all)

    click.echo(f"Loaded {len(total_schemas)} schemas from {len(modules)} modules")
    for schema in total_schemas:
        click.echo(f"  - {schema.name} from {schema.source_class}")

@click.group()
def group():
    pass

group.add_command(hello)
group.add_command(search_mcp)
group.add_command(load_schemas)
# group.add_command(create_fixtures)

if __name__ == '__main__':
    group()
