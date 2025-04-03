import asyncio
from typing import Optional, Dict, Any

import click
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, FloatPrompt, IntPrompt
from rich.syntax import Syntax

from src.core.models import DialogStatus, Dialog
from src.service.pulse_mcp_api import MCPServer
from src.service.logging import logger # Import logger

console = Console()


# Helper function to display messages nicely
def display_message(message):
    role_color = {
        "user": "blue",
        "assistant": "green",
        "system": "yellow",
    }
    color = role_color.get(message.role, "white")
    panel_title = f"[bold {color}]{message.role.capitalize()}[/]"
    if message.model:
        panel_title += f" ({message.model})"

    # Use Syntax for markdown if mime_type indicates it
    if message.mime_type == "text/markdown":
        content = Syntax(message.text, "markdown", theme="default", line_numbers=False)
    else:
        content = message.text

    console.print(Panel(content, title=panel_title, expand=False, border_style=color))

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
@click.option('--verbose', '-v', is_flag=True, help='Show detailed step execution info')
def run_workflow(template_name: str, description: Optional[str] = None, goal: Optional[str] = None, verbose: bool = False):
    """Create and interactively run a workflow from a template."""
    import asyncio
    from src.dependencies import get_workflow_service, get_registry, db_pool
    from src.core.workflow.service import WorkflowService # Import WorkflowService for type hint

    async def _run_workflow():
        await db_pool.open() # Ensure pool is open
        registry = await get_registry().__anext__()
        service: WorkflowService = await get_workflow_service().__anext__() # Type hint service

        template = registry.get_dialog_template(template_name)
        if not template:
            console.print(f"[bold red]Error:[/bold red] Template not found: {template_name}")
            await db_pool.close()
            return

        console.print(f"[bold cyan]Starting workflow:[/bold cyan] {template_name}")
        console.print(f"[cyan]Description:[/cyan] {template.description or 'N/A'}")

        # --- Initial Variable Prompting (Optional - based on analysis) ---
        # This part is complex as it depends on knowing *which* variables are needed *before* the first step.
        # The current engine design handles this by setting WAITING_FOR_INPUT during step execution.
        # We will rely on that mechanism for now.
        initial_data = {} # Start with empty initial data

        try:
            # Create the dialog instance
            dialog = await service.create_dialog_from_template(
                template=template,
                description=description,
                goal=goal,
                initial_data=initial_data # Pass potentially empty initial data
            )
            console.print(f"[cyan]Created Dialog ID:[/cyan] {dialog.id}")

            # --- Interactive Execution Loop ---
            while True:
                # Reload dialog state for latest status and data
                dialog = await service.get_dialog(dialog.id)
                if not dialog:
                    console.print("[bold red]Error:[/bold red] Dialog disappeared unexpectedly.")
                    break

                current_step = dialog.get_current_step()
                step_name = current_step.name if current_step else "None (End)"
                console.rule(f"[bold]Current State: {dialog.current_state} | Status: {dialog.status} | Next Step: {step_name}[/]")

                if dialog.status == DialogStatus.WAITING_FOR_INPUT:
                    console.print("[yellow]Workflow waiting for input...[/]")
                    user_input_data = {}
                    missing_vars = dialog.workflow_data.missing_variables or []

                    if 'user_input' in missing_vars:
                        # General user_input step
                        prompt_text = "Please provide input:"
                        # Try to get prompt text from the current step if it's a UserInputStep
                        if current_step and isinstance(current_step, UserInputStep):
                             # Render prompt template if available
                            if current_step.template:
                                try:
                                    prompt_template = registry.get_prompt(current_step.template)
                                    if prompt_template:
                                        # Combine dialog variables and step results for rendering context
                                        render_context = {**dialog.workflow_data.variables, **dialog.workflow_data.step_results}
                                        prompt_text = await prompt_template.render(render_context)
                                    else:
                                        prompt_text = current_step.prompt or prompt_text # Fallback to static prompt
                                except Exception as e:
                                    logger.warning(f"Could not render prompt template {current_step.template}: {e}")
                                    prompt_text = current_step.prompt or prompt_text # Fallback
                            else:
                                prompt_text = current_step.prompt or prompt_text

                        user_input_data = Prompt.ask(f"[bold yellow]Input required[/]: {prompt_text}")
                        # Clear only 'user_input' from missing vars if that's what we prompted for
                        dialog.workflow_data.missing_variables = [v for v in missing_vars if v != 'user_input']

                    elif missing_vars:
                        # Specific variables needed (e.g., for prompt template)
                        collected_vars = {}
                        for var_name in missing_vars:
                            # Basic type prompting - could be enhanced by schema inspection
                            if "number" in var_name.lower() or (current_step and current_step.output_schema == "number"):
                                collected_vars[var_name] = FloatPrompt.ask(f"[bold yellow]Input required for '{var_name}'[/] (number)")
                            elif "int" in var_name.lower() or (current_step and current_step.output_schema == "integer"):
                                 collected_vars[var_name] = IntPrompt.ask(f"[bold yellow]Input required for '{var_name}'[/] (integer)")
                            else:
                                collected_vars[var_name] = Prompt.ask(f"[bold yellow]Input required for '{var_name}'[/]")
                        user_input_data = collected_vars
                        # Clear the variables we just prompted for
                        dialog.workflow_data.missing_variables = [] # Assume we got all needed now

                    # Provide the input back to the workflow service
                    console.print("[cyan]Submitting input to workflow...[/]")
                    await service.provide_user_input(dialog.id, user_input_data)
                    # Loop continues, will re-fetch dialog state

                elif dialog.is_complete() or dialog.current_state == 'end':
                    console.print("[bold green]Workflow finished.[/]")
                    break
                elif dialog.status == DialogStatus.FAILED:
                     console.print("[bold red]Workflow failed.[/]")
                     if dialog.error:
                         console.print(f"[red]Error:[/red] {dialog.error}")
                     if dialog.workflow_data and dialog.workflow_data.errors:
                         console.print("[red]Step Errors:[/red]")
                         for err in dialog.workflow_data.errors:
                             console.print(f"- {err}")
                     break
                else:
                    # Execute the next step
                    if current_step:
                        console.print(f"[cyan]Executing step:[/cyan] '{current_step.name}' ({current_step.type})")
                    else:
                         console.print("[yellow]No current step found, attempting to finalize...[/]") # Should ideally transition to end

                    exec_result = await service.engine.execute_next_step(dialog)

                    if verbose:
                        console.print(f"[grey]Step Result:[/grey] {exec_result}")

                    if not exec_result.success and exec_result.message:
                         console.print(f"[bold red]Step Execution Error:[/bold red] {exec_result.message}")
                         # The loop will continue and check the dialog status (likely FAILED)

                    # --- Display new messages ---
                    # Fetch the latest dialog state again to show messages added by the step
                    updated_dialog = await service.get_dialog(dialog.id)
                    if updated_dialog:
                        # Determine messages added since the last iteration (simple approach)
                        # A more robust way would track message IDs seen
                        num_messages_before = len(dialog.messages)
                        new_messages = updated_dialog.messages[num_messages_before:]
                        if new_messages:
                            console.print("[bold cyan]New Messages:[/]")
                            for msg in new_messages:
                                display_message(msg)
                        dialog = updated_dialog # Use the updated dialog for the next iteration
                    else:
                        console.print("[bold red]Error:[/bold red] Failed to fetch updated dialog state after step execution.")
                        break

                    await asyncio.sleep(0.1) # Small delay

            console.rule("[bold]Workflow Summary[/]")
            final_dialog = await service.get_dialog(dialog.id) # Get final state
            if final_dialog:
                console.print(f"[bold]Dialog ID:[/bold] {final_dialog.id}")
                console.print(f"[bold]Final Status:[/bold] {final_dialog.status}")
                console.print(f"[bold]Final State:[/bold] {final_dialog.current_state}")
                if final_dialog.workflow_data and final_dialog.workflow_data.step_results:
                    console.print("[bold]Step Results:[/bold]")
                    console.print(final_dialog.workflow_data.step_results)
                if final_dialog.workflow_data and final_dialog.workflow_data.variables:
                    console.print("[bold]Final Variables:[/bold]")
                    console.print(final_dialog.workflow_data.variables)
            else:
                 console.print("[bold red]Could not fetch final dialog state.[/bold red]")


        except Exception as e:
            logger.exception("An error occurred during workflow execution:") # Log full traceback
            console.print(f"[bold red]Critical Error:[/bold red] {str(e)}")
        finally:
            console.print("[cyan]Closing database connection...[/]")
            await db_pool.close()

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
