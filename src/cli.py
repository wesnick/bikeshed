import asyncio
from typing import Optional

import click
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt

from service.pulse_mcp_api import MCPServer

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
    from service.pulse_mcp_api import PulseMCPAPI

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
    details = [f"[bold cyan]Name:[/bold cyan] {server.name}"]

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


@click.command()
@click.argument('template_name')
@click.option('--description', '-d', help='Optional description override')
@click.option('--goal', '-g', help='Optional goal override')
def run_workflow(template_name: str, description: Optional[str] = None, goal: Optional[str] = None):
    """Create and run a workflow from a template."""
    import asyncio
    from src.dependencies import get_workflow_service, get_registry

    async def _run_workflow():
        # Load registry

        registry = await get_registry().__anext__()
        service = await get_workflow_service().__anext__()

        template = registry.get_dialog_template(template_name)
        if not template:
            console.print(f"[bold red]Error:[/bold red] Template not found: {template_name}")
            return

        with (console.status(f"Creating and running workflow from template '{template_name}'...")):
            try:
                dialog = await service.create_dialog_from_template(
                    template=template,
                    initial_data ={
                        'variables': {
                            'initial_idea': 'Chuckee cheese'
                        }
                    }
                )

                await service.run_workflow(dialog)

                print("Updated diagram saved")

                # # Run the workflow
                # step = dialog.get_current_step()
                # while step:
                #     await workflow_service.execute_next_step(dialog)
                #     step = dialog.get_current_step()
                #
                # # Ensure any remaining resources are cleaned up
                # await asyncio.sleep(0.1)  # Small delay to allow async tasks to complete
                #
                console.print("[bold green]Workflow completed successfully![/bold green]")
                console.print(f"[bold]Dialog ID:[/bold] {dialog.id}")
                console.print(f"[bold]Status:[/bold] {dialog.status}")
                console.print(f"[bold]Final state:[/bold] {dialog.current_state}")

            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {str(e)}")

    asyncio.run(_run_workflow())

@click.command()
@click.argument('directory_path')
def add_root(directory_path: str):
    """Add a directory as a root and scan its contents."""
    import asyncio
    from src.dependencies import get_db, db_pool
    from src.core.roots.scanner import FileScanner

    async def _add_root(directory_path: str):
        await db_pool.open()
        async with get_db() as conn:
            scanner = FileScanner(conn)
            try:
                await scanner.create_root_and_scan(directory_path)
                console.print(f"[bold green]Successfully scanned directory '{directory_path}'[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {str(e)}")
            finally:
                await db_pool.close()


    asyncio.run(_add_root(directory_path))


@click.group()
def group():
    pass

group.add_command(hello)
group.add_command(search_mcp)
group.add_command(run_workflow)
group.add_command(add_root)


if __name__ == '__main__':
    group()
