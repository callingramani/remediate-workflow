# Remediate Workflow

**Remediate Workflow** is a containerized microservice designed to automate the detection and remediation of vulnerable Python packages. It goes beyond listing CVEs by actively simulating upgrades in isolated environments to identify safe versions and integrates with LLMs to facilitate automated patching.

![License](https://img.shields.io/badge/license-MIT-blue) ![Python](https://img.shields.io/badge/python-3.11-blue) ![Docker](https://img.shields.io/badge/docker-compose-green) ![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)

## Features

* **Deep Scanning**: Utilizes `pip-audit` to detect known vulnerabilities (CVEs) in Python dependencies.
* **Automated Remediation**:
    * **Auto-Upgrade**: Automatically checks available PyPI versions to find a release with zero vulnerabilities.
    * **Smart Replacements**: Suggests alternative packages (e.g., replacing `requests` with `httpx`) if the current package cannot be fixed, based on a configurable `replacements.json`.
* **Async Architecture**: Built with FastAPI, Redis, and RQ to handle long-running scanning jobs asynchronously without blocking the API.
* **Workflow Automation**: Includes a pre-configured n8n workflow that:
    * Enqueues jobs and polls for results.
    * Uses OpenAI to analyze vulnerability reports.
    * Can automatically create GitHub branches and Pull Requests with the applied fix.
* **Dockerized**: Fully containerized setup using Docker Compose to orchestrate the API, Worker, Redis, and n8n services.

---

## Architecture

The system consists of four main services orchestrated by Docker Compose:

1.  **`remediate` (FastAPI)**: The application entry point. It accepts job requests and provides status updates.
2.  **`worker` (RQ Worker)**: Handles the core logic. It spawns isolated virtual environments (`venv`), runs `pip-audit`, and determines the optimal remediation path.
3.  **`redis`**: Acts as the message broker for the asynchronous job queue.
4.  **`n8n`**: A workflow automation tool used to integrate the scanner with external services like OpenAI and GitHub.

---

## Getting Started

### Prerequisites

* Docker and Docker Compose installed on your machine.
* (Optional) An OpenAI API Key is required if using the LLM features within the n8n workflow.

### Installation & Usage

1.  **Clone and Run**

    Clone the repository and start the services in detached mode:

    ```bash
    git clone [https://github.com/callingramani/remediate-workflow.git](https://github.com/callingramani/remediate-workflow.git)
    cd remediate-workflow

    # Build and start services in the background
    docker compose up --build -d
    ```

    The services will be available at the following endpoints:
    * **API**: `http://localhost:8000`
    * **API Documentation**: `http://localhost:8000/docs`
    * **n8n Automation**: `http://localhost:5678`

2.  **Submit a Remediation Job**

    You can interact with the API directly using `curl`. The following command initiates a scan for a specific package version:

    ```bash
    curl -X POST http://localhost:8000/jobs \
      -H "Content-Type: application/json" \
      -d '{
        "mode": "package",
        "input": "django==3.2.6"
      }'
    ```

    **Response:**
    ```json
    {
      "job_id": "a075da5c-6aac-4bd8-b104-31dd2322fbfc",
      "status": "queued",
      "rq_job_id": "..."
    }
    ```

3.  **Check Job Status & Get Results**

    Poll the status using the `job_id` returned from the previous step. Once completed, the response will include the remediation details.

    ```bash
    curl http://localhost:8000/jobs/a075da5c-6aac-4bd8-b104-31dd2322fbfc
    ```

    **Response (Completed):**
    ```json
    {
      "job_id": "a075da5c-6aac-4bd8-b104-31dd2322fbfc",
      "status": "completed",
      "updated": {
        "package": "django",
        "selected_version": "3.2.25",
        "candidates": [
           { "version": "3.2.25", "high_count": 0 }
        ]
      },
      "updated_path": "/app/data/jobs/.../updated_package.json",
      "report_path": "/app/data/jobs/.../report.md"
    }
    ```

---

## n8n Workflow Integration

This repository includes an `n8n.json` file that defines an automated workflow for security remediation.

### Workflow Logic
1.  **Webhook Trigger**: Listens for incoming requests to remediate a package.
2.  **API Call**: Sends a request to the `remediate` service to enqueue a job.
3.  **Wait & Poll**: Monitors the job status until completion.
4.  **Analysis**: Passes the scan results to OpenAI (GPT-4) to generate a summary and determine confidence levels for the fix.
5.  **Git Operations**: (Configurable) Creates a new Branch and Pull Request on GitHub with the recommended changes.

### Setup
1.  Navigate to `http://localhost:5678` in your browser.
2.  Select **"Import Workflow"** and upload the `n8n.json` file from the root of this repository.
3.  Configure your credentials within n8n for:
    * **OpenAI** (required for the analysis node).
    * **GitHub** (required if enabling the PR creation nodes).
4.  Activate the workflow to start listening for webhooks.

---

## Project Structure

```text
.
├── docker-compose.yml       # Service orchestration configuration
├── n8n.json                 # n8n workflow definition
├── .gitignore               # Git ignore rules
├── remediate_service/       # Main Python Service directory
│   ├── Dockerfile           # Docker build instructions
│   ├── requirements.txt     # Python dependencies
│   └── app/                 # Application source code
│       ├── api.py           # FastAPI route definitions
│       ├── main.py          # Application entrypoint
│       ├── remediator.py    # Core logic: venv management, installation, auditing
│       ├── reporter.py      # Markdown report generation utility
│       ├── scanners.py      # Wrapper for pip-audit CLI
│       ├── worker.py        # RQ worker tasks for async processing
│       ├── utils.py         # General utility functions
│       └── replacements.json # Configuration for package replacements
└── README.md