# 🛡️ RemediateFlow: Open Source Package Vulnerability Scanner & Auto-Fixer

**RemediateFlow** is a containerized microservice that automates the detection and remediation of vulnerable Python packages. Unlike standard scanners that just list CVEs, this service actively simulates upgrades in isolated environments to find the *best* safe version and integrates with LLMs to automate the fix.

![License](https://img.shields.io/badge/license-MIT-blue) ![Python](https://img.shields.io/badge/python-3.11-blue) ![Docker](https://img.shields.io/badge/docker-compose-green) ![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)

## 🚀 Key Features

* **🔍 Deep Scanning**: Uses [`pip-audit`](https://pypi.org/project/pip-audit/) to detect known vulnerabilities (CVEs) in your Python dependencies.
* **🧠 Smart Remediation**:
    * **Auto-Upgrade**: Automatically checks available PyPI versions to find a release with zero vulnerabilities.
    * **Smart Replacements**: Suggests alternative packages (e.g., `requests` → `httpx`) if the current package is unfixable, based on a configurable `replacements.json`.
* **⚡ Async Architecture**: Built with **FastAPI**, **Redis**, and **RQ** to handle heavy scanning jobs asynchronously without blocking your API.
* **🤖 AI-Powered Workflow**: Includes a pre-configured **n8n workflow** that:
    * Enqueues jobs and waits for results.
    * Uses **OpenAI** to interpret the vulnerability report.
    * Can automatically create GitHub branches and Pull Requests with the fix.
* **🐳 Fully Dockerized**: One command to spin up the API, Workers, Redis, and n8n.

---

## 🏗️ Architecture

The system consists of four main services orchestrated by Docker Compose:

* **`remediate` (FastAPI)**: The entry point. Accepts job requests and provides status updates.
* **`worker` (RQ Worker)**: Performs the heavy lifting. Spawns isolated `venv`s, runs `pip-audit`, and determines the best remediation path.
* **`redis`**: Message broker for the async job queue.
* **`n8n`**: Workflow automation tool to integrate the scanner with LLMs (OpenAI) and version control (GitHub).

---

## 🛠️ Getting Started

### Prerequisites
* Docker & Docker Compose installed on your machine.
* (Optional) An OpenAI API Key if you want to use the LLM features in n8n.

### Installation & Usage

1.  **Clone and Run**
    
    Clone the repository and start the services in detached mode:
    ```bash
    git clone [https://github.com/yourusername/remediate-workflow.git](https://github.com/yourusername/remediate-workflow.git)
    cd remediate-workflow
    
    # Build and start services in the background
    docker compose up --build -d
    ```
    
    Services will be available at:
    * **API**: `http://localhost:8000`
    * **API Docs (Swagger)**: `http://localhost:8000/docs`
    * **n8n**: `http://localhost:5678`

2.  **Submit a Remediation Job**
    
    You can interact with the API directly via `curl`. Here is how to scan a specific package (e.g., a vulnerable version of Django):
    
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
    
    Poll the status using the `job_id` you received from the previous step:
    
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

## 🤖 AI Integration (n8n Workflow)

This repo includes a powerful **n8n workflow** (`n8n.json`) that acts as an intelligent security engineer.

### How it works
1.  **Webhook Trigger**: Receives a request to remediate a package.
2.  **API Call**: Calls the `remediate` service to start the job.
3.  **Wait & Poll**: Waits for the worker to finish the scan.
4.  **LLM Analysis**: Feeds the scan results (JSON) into **OpenAI (GPT-4)** to generate a summary and decide if the fix is confident enough to apply.
5.  **Git Ops**: (Configurable) Creates a Branch and Pull Request on GitHub with the fix.

### Setup
1.  Open n8n at `http://localhost:5678`.
2.  Click **"Import Workflow"** and upload the `n8n.json` file from this repository.
3.  Configure your credentials in n8n for:
    * **OpenAI** (for the analysis node).
    * **GitHub** (if you enable the PR creation nodes).
4.  Activate the workflow.

---