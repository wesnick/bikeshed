import asyncio
import click
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from typing import Optional

from src.dependencies import get_registry
from src.service.pulse_mcp_api import PulseMCPAPI, MCPServer


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

@click.command()
@click.option('--directories', '-d', multiple=True,
              help='Directories to scan for templates (format: alias:path)')
def load_templates(directories):
    """Load templates from specified directories into the registry."""
    from src.core.registry import Registry
    from src.core.config_loader import TemplateLoader
    from src.dependencies import get_jinja

    # Create registry and Jinja environment
    registry = Registry()

    loader = TemplateLoader(registry, get_jinja().templates.env)

    # Parse directory configs
    directory_configs = []
    for dir_spec in directories:
        parts = dir_spec.split(':', 1)
        if len(parts) != 2:
            click.echo(f"Invalid directory specification: {dir_spec}. Use format 'alias:path'")
            continue

        alias, path = parts
        directory_configs.append({'alias': alias, 'path': path})

    # Load templates
    prompts = loader.load_from_directories(directory_configs)

    click.echo(f"Loaded {len(prompts)} templates from {len(directory_configs)} directories")
    for prompt in prompts:
        click.echo(f"  - {prompt.name} with variables: {prompt.arguments}")

@click.command()
@click.argument('files', nargs=-1, required=True)
@click.option('--validate-only', is_flag=True, help="Only validate templates without registering them")
def load_session_templates(files, validate_only):
    """Load session templates from YAML files."""
    from src.core.registry import Registry
    from src.core.config_loader import SessionTemplateLoader
    from rich.table import Table

    registry = Registry()
    loader = SessionTemplateLoader(registry)

    total_templates = {}
    for file_path in files:
        templates = loader.load_from_file(file_path)
        total_templates.update(templates)

    # Create a nice summary table
    table = Table(title="Session Template Loading Results")
    table.add_column("File", style="cyan")
    table.add_column("Templates", style="green")
    table.add_column("Status", style="yellow")

    for file_path in files:
        file_templates = loader.load_from_file(file_path)
        status = f"[green]✓ {len(file_templates)} loaded" if file_templates else "[red]✗ No valid templates"
        table.add_row(file_path, ", ".join(file_templates.keys()) or "None", status)

    console.print(table)

    if total_templates:
        console.print(f"[green]Successfully loaded {len(total_templates)} templates:[/green]")
        for name in total_templates:
            console.print(f"  - {name}")
    else:
        console.print("[red]No valid templates were loaded.[/red]")
        console.print("Check the logs for detailed validation errors.")

    if not validate_only and total_templates:
        # Register templates in registry (placeholder for future implementation)
        registered_names = loader.register_templates(total_templates)
        console.print(f"[green]Registered {len(registered_names)} templates in the registry.[/green]")


@click.command()
@click.argument('template_name')
@click.option('--description', '-d', help='Optional description override')
@click.option('--goal', '-g', help='Optional goal override')
def run_workflow(template_name: str, description: Optional[str] = None, goal: Optional[str] = None):
    """Create and run a workflow from a template."""
    import asyncio
    from src.dependencies import get_workflow_service

    async def _run_workflow():
        # Load registry

        registry = await get_registry().__anext__()
        service = await get_workflow_service().__anext__()

        template = registry.get_session_template(template_name)
        if not template:
            console.print(f"[bold red]Error:[/bold red] Template not found: {template_name}")
            return

        with (console.status(f"Creating and running workflow from template '{template_name}'...")):
            try:
                session = await service.create_session_from_template(
                    template=template,
                    initial_data ={
                        'variables': {
                            'initial_idea': 'Chuckee cheese'
                        }
                    }
                )

                await service.run_workflow(session)

                print("Updated diagram saved")

                # # Run the workflow
                # step = session.get_current_step()
                # while step:
                #     await workflow_service.execute_next_step(session)
                #     step = session.get_current_step()
                #
                # # Ensure any remaining resources are cleaned up
                # await asyncio.sleep(0.1)  # Small delay to allow async tasks to complete
                #
                console.print("[bold green]Workflow completed successfully![/bold green]")
                console.print(f"[bold]Session ID:[/bold] {session.id}")
                console.print(f"[bold]Status:[/bold] {session.status}")
                console.print(f"[bold]Final state:[/bold] {session.current_state}")

            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {str(e)}")

    asyncio.run(_run_workflow())


@click.command()
@click.argument('description')
@click.option('--goal', '-g', help='Optional goal for the session')
def create_ad_hoc(description: str, goal: Optional[str] = None):
    """Create a new ad-hoc session without a workflow."""
    import asyncio
    from src.dependencies import async_session_factory
    from src.service.session import SessionService

    async def _create_ad_hoc():
        session_service = SessionService()

        async with async_session_factory() as db:
            with console.status("Creating ad-hoc session..."):
                try:
                    session = await session_service.create_ad_hoc_session(db, description, goal)

                    # Display session info
                    console.print(f"[bold green]Ad-hoc session created:[/bold green] {session.id}")
                    console.print(f"[bold]Description:[/bold] {session.description}")
                    if session.goal:
                        console.print(f"[bold]Goal:[/bold] {session.goal}")
                    console.print(f"[bold]Status:[/bold] {session.status}")

                except Exception as e:
                    console.print(f"[bold red]Error:[/bold red] {str(e)}")

    asyncio.run(_create_ad_hoc())

@click.command()
@click.argument('directory_path')
def add_root(directory_path: str):
    """Add a directory as a root and scan its contents."""
    import asyncio
    from src.dependencies import async_session_factory
    from src.core.roots.scanner import FileScanner

    async def _add_root(directory_path: str):
        scanner = FileScanner(async_session_factory)
        try:
            await scanner.create_root_and_scan(directory_path)
            console.print(f"[bold green]Successfully scanned directory '{directory_path}'[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")


    asyncio.run(_add_root(directory_path))


@click.group()
def group():
    pass

@click.command()
@click.option("--limit", default=100, help="Maximum number of blobs to list")
@click.option("--offset", default=0, help="Offset for pagination")
def list_blobs(limit: int, offset: int):
    """List all blobs in the database"""
    import asyncio
    from src.service.blob_service import BlobService
    from src.dependencies import get_db

    async def _list_blobs():
        blob_service = BlobService()
        async for db in get_db():
            blobs = await blob_service.list_blobs(db, limit, offset)
            if not blobs:
                click.echo("No blobs found.")
                return
            
            click.echo(f"Found {len(blobs)} blobs:")
            for blob in blobs:
                size = f"{blob.byte_size / 1024:.1f} KB" if blob.byte_size else "Unknown size"
                click.echo(f"- {blob.name} ({blob.content_type}, {size})")
                if blob.description:
                    click.echo(f"  Description: {blob.description}")
                click.echo(f"  ID: {blob.id}")
                click.echo(f"  Created: {blob.created_at}")
                click.echo("")

    asyncio.run(_list_blobs())

@click.command()
@click.argument("file_path", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("--name", help="Name for the blob (defaults to filename)")
@click.option("--description", help="Description for the blob")
def upload_blob(file_path: str, name: str = None, description: str = None):
    """Upload a file as a blob"""
    import asyncio
    import os
    import mimetypes
    from src.service.blob_service import BlobService
    from src.dependencies import get_db

    async def _upload_blob():
        blob_service = BlobService()
        
        # Determine the file name and content type
        file_name = name or os.path.basename(file_path)
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"
        
        click.echo(f"Uploading {file_path} as {file_name} ({content_type})...")
        
        with open(file_path, "rb") as file:
            async for db in get_db():
                blob = await blob_service.create_blob(
                    conn=db,
                    name=file_name,
                    content_type=content_type,
                    file=file,
                    description=description
                )
                
                size = f"{blob.byte_size / 1024:.1f} KB" if blob.byte_size else "Unknown size"
                click.echo(f"Uploaded successfully!")
                click.echo(f"- ID: {blob.id}")
                click.echo(f"- Size: {size}")
                click.echo(f"- SHA256: {blob.sha256}")
                click.echo(f"- URL: {blob.content_url}")

    asyncio.run(_upload_blob())

group.add_command(hello)
group.add_command(search_mcp)
group.add_command(load_schemas)
group.add_command(load_templates)
group.add_command(load_session_templates)
group.add_command(run_workflow)
group.add_command(create_ad_hoc)
group.add_command(add_root)
group.add_command(list_blobs)
group.add_command(upload_blob)

if __name__ == '__main__':
    group()
