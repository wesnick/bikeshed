import click

@click.command()
def hello():
    click.echo('Hello World!')

@click.group()
def group():
    pass

group.add_command(hello)

if __name__ == '__main__':
    group()