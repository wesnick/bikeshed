# BikeShed

### WIP: This project should be considered a work-in-progress.  Currently, Linux Only

Bikeshed, a place to sweat the details, however trivial.

## Overview

**BikeShed** is an experimental project built as a Model Context Protocol (MCP) client. There are many like it, this is mine.

This project aims to provide a flexible playground creating reusable context sets: instructions, tools, resources.  The main goal is to be able to experiment with simple workflows to create artifacts.  Eventually, a goal it to generate a detailed specification for a workflow that can be "compiled" into a executable application.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Features

- **Experimental**: BikeShed serves as a playground for developers interested in experimenting with MCP-related concepts.
- **Declarative Workflow Syntax**: Trying to make building simple workflow components using YAML easy
- **Context Management**: Tools for managing and manipulating model contexts.

## Installation

To get started with BikeShed, follow these steps:

1. **Clone the repository**:

```bash
git clone https://github.com/wesnick/bikeshed.git
cd bikeshed
```

2. **Install dependencies**:

You need uv, rust, go, npm, deno installed.  Sorry, this is a developer app so these are table stakes.

OS dependencies, assuming Debian-flavored distro

```bash
sudo apt-get install libmagic1 graphviz graphviz-dev
```
Python

```bash
uv sync
```

Rust
```bash
cargo install just
cargo install monolith
```

Golang

```bash
go install github.com/stripe/pg-schema-diff/cmd/pg-schema-diff@latest
```

Node
```bash
npm install
```

Deno
```bash
curl -fsSL https://deno.land/install.sh | sh
```

3. **Run the project**:

From here on out, use `just`

```bash
just setup-env  # be sure to edit your .env
just docup
# Dev has 3 processes
just fastapi-dev
just frontend-dev
just arq-dev
```

Make sure to check the [docs/project.md] for additional info.

## Usage

TBD

## Contributing

We appreciate contributions to BikeShed! If you're interested in contributing, please fork the repository and submit a pull request. You can also report issues or propose features through the GitHub issues page.

1. Fork it (https://github.com/wesnick/bikeshed/fork)
2. Create your feature branch (`git checkout -b feature/MyNewFeature`)
3. Commit your changes (`git commit -m 'Add some feature'`)
4. Push to the branch (`git push origin feature/MyNewFeature`)
5. Create a new Pull Request

## License

BikeShed is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

## Contact

For questions, feedback, or inquiries about BikeShed, please reach out:

- **GitHub Issues**: https://github.com/wesnick/bikeshed/issues

---

**Disclaimer**: BikeShed is an experimental project and may contain bugs or unfinished features. It is intended for exploration and should be used with caution in production environments.
