# **Architectural Blueprint for Enterprise Agentic Systems on AMD Ryzen AI Max 395+**

## **1\. Executive Summary**

The convergence of high-performance localized compute, advanced open-source large language models (LLMs), and agentic orchestration frameworks has enabled a new paradigm in enterprise software: the autonomous, privacy-preserving Local AI Workstation. This report details the architectural design, implementation strategies, and operational deployment of an enterprise-grade agentic application hosted on the AMD Ryzen AI Max 395+ ("Strix Halo") platform.

The proposed solution leverages the **Qwen3-14b-instruct** model as the cognitive core, orchestrated by **LangGraph** for stateful, cyclic agent workflows. The system is designed to run locally on **Ubuntu Linux**, utilizing the massive unified memory architecture (UMA) of the Strix Halo APU to prioritize GPU (ROCm) inference, with intelligent fallback mechanisms to the NPU (XDNA 2\) and CPU (Zen 5). This architecture explicitly addresses the requirement for a robust, sovereign AI capability that integrates seamlessly with legacy enterprise systems—including Customer Relationship Management (CRM), Enterprise Resource Planning (ERP), Manufacturing Execution Systems (MES), and Office Automation (OA)—via the standardized **Model Context Protocol (MCP)**.

Key architectural pillars include:

1. **Hardware Acceleration:** Native ROCm 7.2 integration for the RDNA 3.5 GPU (gfx1150/1151) drives high-throughput token generation via vLLM, leveraging the 96GB of addressable Video RAM (VRAM) to host full-precision models and large context windows without offloading penalties.  
2. **Orchestration:** A multi-agent Supervisor architecture built on LangGraph manages specialized sub-agents (Knowledgebase, ComfyUI, Email, ERP/CRM/MES Integrators), enabling complex, multi-step reasoning capabilities unavailable in linear chat applications.  
3. **Interoperability:** Adoption of the MCP standardizes connections between AI agents and legacy systems, reducing integration brittleness and enhancing security by isolating authentication logic from the probabilistic AI layer.  
4. **Observability:** A comprehensive OpenTelemetry-based pipeline (OpenLLMetry) tracks Service Level Agreements (SLAs), accuracy, and user interaction metrics, ensuring the system is production-ready and auditable.  
5. **User Experience:** Integration of **LangFlow** provides a low-code, drag-and-drop builder interface for rapid prototyping, coupled with a production-grade chat interface for end-users.

This report serves as an exhaustive guide for systems architects and developers to build, deploy, and maintain this high-performance local AI ecosystem.

## ---

**2\. Infrastructure Layer: Unleashing the Strix Halo**

The foundation of this agentic application is the AMD Ryzen AI Max 395+, a processor designed to blur the lines between mobile APUs and high-end desktop workstations. Successfully leveraging this hardware requires a meticulous setup of the operating system, kernel, and compute stack to expose the heterogeneous compute elements (CPU, GPU, NPU) to the application layer.

### **2.1. Hardware Analysis: AMD Ryzen AI Max 395+**

The Ryzen AI Max 395+ (codenamed "Strix Halo") represents a significant shift in x86 architecture, specifically beneficial for LLM workloads due to its memory subsystem.1 Unlike traditional workstations that rely on discrete GPUs (dGPUs) connected via PCIe—introducing bandwidth bottlenecks and strict VRAM capacity limits—the Strix Halo utilizes a unified memory architecture (UMA).

**Table 1: Critical Hardware Specifications for AI Workloads**

| Feature | Specification | Implication for Agentic AI |
| :---- | :---- | :---- |
| **Processor Architecture** | 16x "Zen 5" CPU Cores | High-performance handling of classical logic, API routing (FastAPI), and vector database management. |
| **Graphics Architecture** | 40x RDNA 3.5 Compute Units | Massive parallel throughput for LLM inference (vLLM) and Image Generation (ComfyUI). |
| **AI Accelerator** | XDNA 2 NPU (50+ TOPS) | Highly efficient, low-power inference for continuous background tasks like RAG embeddings. |
| **Memory Capacity** | Up to 128GB LPDDR5X-8000 | Allows loading Qwen3-14b (FP16), ComfyUI models, and vector indices simultaneously in RAM. |
| **Video Memory (VRAM)** | Up to 96GB Allocation | Eliminates the "Out of Memory" issues common with consumer GPUs; supports massive context windows (128k). |
| **TDP** | Configurable (Up to 120W) | balances high performance with workstation-class thermal management. |

The critical advantage here is the memory configuration. Most consumer GPUs max out at 24GB VRAM. An enterprise agent running Qwen3-14b at FP16 precision requires approximately 28GB for weights alone, plus significant overhead for the KV cache (Key-Value cache) to support long context windows.1 The Strix Halo’s ability to allocate up to 96GB of system RAM as dedicated VRAM allows the entire model, a large KV cache, and additional vision models to reside in high-speed memory, enabling low-latency switching between text generation and image reasoning tasks.

### **2.2. Operating System & Kernel Configuration**

**Distribution:** **Ubuntu 24.04 LTS (Noble Numbat)** is the recommended operating system. It offers the best compatibility with the latest Linux kernels required for RDNA 3.5 support and is the target platform for ROCm 7.2.2

**Kernel Setup:**

The Strix Halo’s graphics and NPU subsystems require modern kernel interfaces. While Ubuntu 24.04 ships with a 6.8 kernel, full stability for the RDNA 3.5 (gfx1150/gfx1151) architecture often requires a newer kernel or specific OEM optimizations.

1. **Kernel Version:** Ideally, use Linux Kernel **6.10+** or the linux-oem-24.04 meta-package to ensure all display and compute drivers are correctly initialized.  
2. **IOMMU Configuration:** To facilitate efficient memory sharing between the CPU and GPU without excessive overhead, IOMMU groups must be cleanly defined. In /etc/default/grub, the parameter iommu=pt (pass-through) is recommended to improve virtualization performance if parts of the stack are containerized.

**Memory Allocation Strategy:**

Maximizing the VRAM allocation is the single most important BIOS configuration step for this project.

1. **BIOS Configuration:** Access the system BIOS (typically F2/Del at boot). Navigate to *Advanced \> NBIO Common Options \> GFX Configuration*. Set **IGPU Memory Mode** to **Game Optimized** or **Manual**.  
   * If **Manual**, set the Frame Buffer Size to **96GB**.  
   * This reserves 96GB of the 128GB total RAM exclusively for the GPU. The remaining 32GB is sufficient for the OS, Docker containers, PostgreSQL database, and application logic.  
2. **GART/GTT Configuration:** On Linux, the Graphics Translation Table (GTT) maps system memory for GPU access. For large VRAM allocations, the default GTT size is often insufficient.  
   * Edit /etc/default/grub:  
     Bash  
     GRUB\_CMDLINE\_LINUX\_DEFAULT="quiet splash amdgpu.gttsize=8192 hugepages=2048"

   * **Implication:** amdgpu.gttsize=8192 ensures the driver can map massive memory pages. hugepages=2048 reduces TLB (Translation Lookaside Buffer) misses, slightly improving inference latency for large models.  
   * Run sudo update-grub and reboot.

### **2.3. ROCm 7.2 Installation and Enablement**

ROCm (Radeon Open Compute) is the software stack that translates the agent's neural network operations into instructions the RDNA 3.5 GPU can execute. ROCm 7.2 is the pivotal release that officially introduces support for the Strix Halo architecture.3

#### **2.3.1. Installation Steps**

A "Hybrid" installation approach is recommended: installing the kernel-mode drivers on the host OS while keeping the user-space libraries (compilers, math libraries) inside Docker containers. This maintains system cleanliness and reproducibility.

1. **Add Repositories:**  
   Bash  
   sudo apt update  
   sudo apt install \-y wget gnupg2  
   wget https://repo.radeon.com/rocm/rocm.gpg.key \-O \- | sudo apt-key add \-  
   echo 'deb \[arch=amd64\] https://repo.radeon.com/rocm/apt/7.2 jammy main' | sudo tee /etc/apt/sources.list.d/rocm.list

   Note: While Ubuntu 24.04 is "noble," ROCm repositories often initially target the previous LTS "jammy". This is generally compatible for user-space libraries.2  
2. **Install Kernel Drivers:** Use the amdgpu-install script to install the driver. Crucially, use the \--no-dkms flag if running a very new kernel, as the in-tree drivers are often more stable for pre-release hardware than the DKMS modules.5  
   Bash  
   sudo apt update  
   sudo apt install./amdgpu-install\_6.0.60002-1\_all.deb  
   sudo amdgpu-install \--usecase=graphics,rocm \--no-dkms

3. **User Permissions:**  
   Access to the GPU hardware nodes (/dev/kfd and /dev/dri/renderD128) requires specific group membership.  
   Bash  
   sudo usermod \-aG render,video $USER

   A reboot is required after this step.  
4. **Verification:**  
   Verify the installation using rocminfo and rocm-smi.  
   * rocminfo should list the GPU Agent with the name "gfx1150" or "gfx1151".  
   * If rocm-smi shows the GPU temperature and memory usage, the driver is successfully loaded.3

#### **2.3.2. RDNA 3.5 Compatibility Overrides**

The software ecosystem (PyTorch, vLLM) may not yet have pre-compiled binaries specifically for gfx1151. However, the architecture is backward compatible with RDNA 3 (gfx1100). To ensure immediate compatibility with standard libraries, we utilize a robust override mechanism.6

**Environment Variable Override:**

Bash

export HSA\_OVERRIDE\_GFX\_VERSION=11.5.0

This variable instructs the ROCm runtime to expose the hardware as generic RDNA 3.5 compliant, bypassing strict ISA version checks that might otherwise cause the application to abort. This is a critical enabler for running "Day 0" software on Strix Halo hardware.

## ---

**3\. Cognitive Engine: Qwen3-14b and Inference Optimization**

The intelligence of the agentic system is derived from the Large Language Model (LLM). The selection of **Qwen3-14b-instruct** is strategic: it offers a balance of parameter density (intelligence) and computational weight (speed) that fits perfectly within the Strix Halo's envelope, allowing for "Thinking Mode" reasoning without the latency of 70B+ models.8

### **3.1. Model Analysis: Qwen3-14b-instruct**

* **Parameter Count:** 14.8 Billion parameters (Dense). This size is the "sweet spot" for enterprise tasks—capable of complex instruction following (e.g., "Parse this invoice and extract the VAT") while remaining fast enough for real-time interaction.8  
* **Reasoning Capability:** Qwen3 introduces a "Thinking Mode," where the model generates an internal chain-of-thought enclosed in specific tokens before outputting the final answer. This behavior is analogous to OpenAI's o1-preview and is essential for the Supervisor Agent to decompose complex user requests.8  
* **Context Window:** Natively supports 32k tokens, extensible to 128k via YaRN interpolation. This allows the agent to ingest entire manuals or long email threads in a single prompt.8

### **3.2. Serving Backend: vLLM vs. llama.cpp**

To serve this model to the LangGraph agents, an inference server is required. We prioritize **vLLM** for its architectural superiority in high-concurrency environments, with **llama.cpp** as a highly compatible backup.

#### **3.2.1. Primary Engine: vLLM (Optimized for Throughput)**

vLLM utilizes **PagedAttention**, an algorithm that manages the KV cache memory in non-contiguous blocks, similar to OS virtual memory. This is critical for Strix Halo because it prevents memory fragmentation in the 96GB VRAM pool, allowing for larger effective batch sizes and context windows.

**Implementation Strategy:** Given the novelty of gfx1151, installing via pip install vllm may pull binaries incompatible with the hardware. Compiling from source is the reliable path.10

**Compiling vLLM for Strix Halo:**

1. **Clone Repository:**  
   Bash  
   git clone https://github.com/vllm-project/vllm.git  
   cd vllm

2. **Docker Build:** Create a reproducible build environment.  
   Dockerfile  
   \# Dockerfile.rocm  
   FROM rocm/pytorch:rocm6.2\_ubuntu22.04\_py3.10\_pytorch\_2.3.0  
   ENV ROCM\_HOME=/opt/rocm  
   \# Target Strix Halo specifically  
   ENV PYTORCH\_ROCM\_ARCH="gfx1151"  
   \# Fallback to gfx1100 if 1151 compilation fails in PyTorch  
   ENV HSA\_OVERRIDE\_GFX\_VERSION=11.5.0 

   RUN pip install \--upgrade pip build  
   COPY. /app/vllm  
   WORKDIR /app/vllm  
   RUN pip install \-r requirements-rocm.txt  
   RUN python3 setup.py install

3. **Running the Server:**  
   The server command must tune the memory usage to leave room for the system.  
   Bash  
   docker run \--device /dev/kfd \--device /dev/dri \\  
     \--shm-size=16g \\  
     \-p 8000:8000 \\  
     vllm-rocm-strix \\  
     python3 \-m vllm.entrypoints.openai.api\_server \\  
     \--model Qwen/Qwen3-14b-instruct \\  
     \--trust-remote-code \\  
     \--dtype float16 \\  
     \--gpu-memory-utilization 0.85 \\  
     \--max-model-len 32768

   * \--dtype float16: Strix Halo has native FP16 peak performance of \~60 TFLOPS.12 Running in FP16 avoids the quantization loss of Int8, preserving the model's subtle reasoning abilities.  
   * \--gpu-memory-utilization 0.85: Reserves 15% of the 96GB (approx. 14GB) for the OS, ComfyUI, and embedding models.

#### **3.2.2. Backup Engine: llama.cpp (Maximum Compatibility)**

If vLLM encounters instability, llama.cpp offers a robust fallback using GGUF quantization. It is particularly resilient to driver version mismatches.13

**Optimization for Strix Halo:**

Compile with the HIPBLAS flag to enable GPU acceleration.

Bash

make LLAMA\_HIPBLAS=1 AMDGPU\_TARGETS=gfx1151

Run the server with full GPU offload:

Bash

./llama-server \-m models/qwen3-14b-instruct-q4\_k\_m.gguf \-ngl 99 \-c 32768 \--port 8001

The \-ngl 99 flag ensures all transformer layers run on the RDNA 3.5 GPU, utilizing the high-speed unified memory.

### **3.3. NPU and CPU Utilization Strategy**

The original request mandates utilizing NPU/CPU as backups or for auxiliary tasks. The Strix Halo architecture is heterogeneous, and efficient utilization requires assigning workloads to the most appropriate compute unit.

**Table 2: Compute Assignment Strategy**

| Workload | Primary Compute | Backup Compute | Rationale |
| :---- | :---- | :---- | :---- |
| **LLM Inference** (Qwen3) | **GPU (RDNA 3.5)** | CPU (Zen 5\) | GPU provides massive parallelism for token generation. CPU is too slow for real-time 14B inference but works for batch jobs. |
| **Embedding Generation** (RAG) | **NPU (XDNA 2\)** | CPU (Zen 5\) | Embeddings (e.g., bge-m3) are matrix-multiplication heavy but require low latency. The NPU (50 TOPS) is highly efficient here. |
| **Vector Search** (Qdrant) | **CPU (Zen 5\)** | N/A | Vector similarity search is memory-latency bound and relies on AVX-512 instructions, where Zen 5 excels.1 |
| **Image Generation** (ComfyUI) | **GPU (RDNA 3.5)** | CPU (Zen 5\) | Diffusion models are compute-intensive; GPU is mandatory for interactive speeds (\<10s per image). |

To enable NPU utilization for embeddings, we utilize the **Ryzen AI Software** stack (based on ONNX Runtime Vitis AI EP). The embedding model is quantized to Int8 and compiled for the XDNA 2 target, allowing it to run continuously in the background without stealing cycles from the GPU-hosted LLM.

## ---

**4\. Orchestration Layer: LangGraph Architecture**

**LangGraph** is the orchestration engine that transforms the Qwen3 LLM from a passive text generator into an active agentic system. Unlike linear chains (e.g., standard LangChain), LangGraph models the application as a state machine (graph) with nodes (agents/tools) and edges (control flow). This supports loops, persistence, and complex decision-making, which are prerequisites for handling multi-step enterprise tasks.14

### **4.1. Core Concepts and State Schema**

The central nervous system of the agent is the AgentState. This is a strongly typed dictionary that persists throughout the graph's execution, accumulating context.

Python

from typing import TypedDict, Annotated, List, Union  
from langchain\_core.messages import BaseMessage  
import operator

class AgentState(TypedDict):  
    \# Append-only list of messages (User, AI, Tool outputs)  
    messages: Annotated, operator.add\]  
    \# The 'plan' currently being executed, decided by the Supervisor  
    next\_step: str  
    \# Context data retrieved from ERP/CRM to avoid repeated queries  
    customer\_profile: dict  
    order\_details: dict  
    \# Error tracking for retry logic  
    error\_count: int

### **4.2. The Supervisor Architecture**

For this enterprise application, a **Multi-Agent Supervisor** pattern is employed. Rather than a single monolithic agent, a top-level "Supervisor" routes tasks to specialized worker agents. This modularity improves accuracy because each sub-agent is prompted specifically for its domain.16

**The Agents:**

1. **Supervisor:** The router. Uses Qwen3's reasoning mode to parse intent.  
2. **ERP Agent:** Specialized in querying Odoo/SAP. Prompt includes database schemas.  
3. **CRM Agent:** Specialized in Salesforce/HubSpot. Prompt includes sales protocols.  
4. **MES Agent:** Specialized in IoT and Manufacturing data. Prompt includes machine codes.  
5. **Knowledge Agent:** Specialized in RAG (document retrieval).  
6. **Creative Agent:** Specialized in ComfyUI prompt engineering.  
7. **Email Agent:** Specialized in business communication and IMAP/SMTP protocols.

**Routing Logic:**

The Supervisor node executes a prompt:

*"You are a Supervisor. You have access to the following workers:. Given the conversation history, decide who should act next. Output a JSON object with the key 'next' pointing to the worker name, or 'FINISH' if the user's request is satisfied."*

### **4.3. Persistence and Fault Tolerance**

Enterprise workflows often span long periods (e.g., waiting for a human manager to approve an invoice). LangGraph's **Checkpointer** mechanism is essential here.

**Implementation:**

We utilize a local **PostgreSQL** instance to store the state of every active graph.

Python

from langgraph.checkpoint.postgres import PostgresSaver  
from psycopg\_pool import ConnectionPool

\# Connection to local Postgres running in Docker  
DB\_URI \= "postgresql://langgraph:securepass@localhost:5432/state\_db"  
pool \= ConnectionPool(conninfo=DB\_URI)  
checkpointer \= PostgresSaver(pool)

\# Compile graph with persistence  
app \= workflow.compile(checkpointer=checkpointer)

**Benefit:** If the Strix Halo workstation reboots, or if the LangGraph service crashes, the agent resumes execution exactly where it left off upon restart. This provides the "long-running thread" capability required for reliable business automation.14

## ---

**5\. Integration Fabric: The Model Context Protocol (MCP)**

A critical requirement is the integration with legacy apps (CRM, ERP, MES, OA). Hardcoding API calls directly into the LangGraph nodes creates a brittle system where a change in the ERP's API version breaks the AI agent. To solve this, we adopt the **Model Context Protocol (MCP)**.18

MCP is an open standard that standardizes how AI models interact with external data and tools. It creates a clean separation of concerns:

* **MCP Server:** A lightweight service that wraps the legacy system's API (e.g., Odoo XML-RPC) and exposes a standard set of "Tools" and "Resources."  
* **MCP Client:** The LangGraph agent, which connects to the server and dynamically discovers capabilities.

### **5.1. ERP Integration: Odoo (Open Source ERP)**

**Scenario:** The agent needs to check inventory and create sale orders.

**MCP Server Implementation:**

We create a Python-based MCP server (odoo-mcp) using the fastmcp library.

* **Authentication:** The server holds the API keys and handles the XML-RPC login/session management.  
* **Tools Exposed:** check\_product\_stock(sku), create\_quotation(customer\_id, items).  
* **Security:** The AI agent never sees the API keys; it only sees the function signatures.

Python

\# odoo\_mcp\_server.py  
from mcp.server.fastmcp import FastMCP  
import xmlrpc.client

mcp \= FastMCP("OdooERP")

@mcp.tool()  
def check\_stock(product\_name: str) \-\> str:  
    """Queries Odoo to find the quantity on hand for a product."""  
    \#... Odoo XML-RPC logic...  
    return f"Product {product\_name}: 150 units available."

LangGraph connects to this server. When Qwen3 decides to "check stock," it emits a tool call. The MCP client forwards this to the Odoo MCP server, which executes the logic and returns the result.

### **5.2. CRM Integration: Salesforce**

**Scenario:** The agent needs to log a customer interaction or update a lead's status. **MCP Server Implementation:** A similar MCP server (salesforce-mcp) wraps the simple-salesforce Python library.20

* **Tools Exposed:** search\_contact(email), log\_activity(lead\_id, note), update\_stage(opportunity\_id, new\_stage).  
* **Benefit:** If the enterprise switches from Salesforce to HubSpot, developers only need to swap the MCP server. The LangGraph agent's logic ("Look up customer, then log note") remains unchanged.

### **5.3. MES Integration: Shop Floor IoT**

**Scenario:** The agent needs to check if a machine is running or stopped (SLA tracking). **Protocol:** Manufacturing Execution Systems often use low-level protocols like **OPC-UA** or **Modbus**.22 **MCP Server Implementation:**

* **Library:** opcua (Python).  
* **Tools Exposed:** read\_machine\_status(machine\_id), get\_production\_count(job\_id).  
* **Mechanism:** The MCP server maintains a persistent connection to the PLC (Programmable Logic Controller) or OPC-UA aggregator. When the agent requests a status, the server reads the specific node tag (e.g., ns=2;s=Machine1.Status) and returns a human-readable string.23

### **5.4. Office Automation (OA): Email Agents**

**Scenario:** Sending and receiving business correspondence.

**Implementation:**

The Email Agent is a LangGraph node equipped with standard Python imaplib (for reading) and smtplib (for sending) tools.

* **Ingestion:** A background thread (or cron job) polls the IMAP server for unread messages matching specific criteria (e.g., Subject: "Urgent").  
* **Processing:** The email body is extracted and injected into the AgentState.  
* **Drafting:** The Qwen3 model drafts a reply.  
* **Human-in-the-Loop:** Before smtplib is called to send, the workflow pauses (via interrupt\_before=\["send\_email"\]). The draft is presented in the UI for human approval. This prevents the AI from sending hallucinations to clients.24

## ---

**6\. Visual Intelligence: ComfyUI and Computer Vision**

The requirement for **ComfyUI** integration adds a multimodal dimension to the workstation. ComfyUI is a node-based interface for Stable Diffusion, ideal for procedural image generation.

### **6.1. System Integration**

ComfyUI runs as a separate service (typically on port 8188). LangGraph interacts with it via its WebSocket API.25

**Workflow:**

1. **Design:** A user designs a complex image generation workflow in the ComfyUI frontend (e.g., Text-to-Image with a specific LoRA for company branding) and saves it as workflow\_api.json.  
2. **Tool Creation:** A LangGraph tool generate\_marketing\_asset is created.  
3. **Execution:**  
   * The tool accepts a prompt from Qwen3.  
   * It loads the workflow\_api.json template.  
   * It injects the prompt into the text node of the JSON.  
   * It sends the JSON to the ComfyUI backend.  
   * It waits for the generation to complete and retrieves the image filename.

### **6.2. Visual Inspection Agent (MES Context)**

Beyond generation, the system can use **Qwen2.5-VL** (Vision Language Model) or **OpenCV** agents for quality control.27

* **Input:** An image from a shop-floor camera.  
* **Analysis:** The image is passed to the VL model with the prompt: *"Identify any defects in this casting."*  
* **Action:** If a defect is found, the agent uses the MES MCP tool to flag the batch.

## ---

**7\. Observability and Telemetry**

In an enterprise setting, "it works" is insufficient; we must know *how well* it works. We implement a robust telemetry stack using **OpenTelemetry (OTel)**, specifically tuned for LLMs via **OpenLLMetry**.29

### **7.1. The Telemetry Pipeline**

1. **Instrumentation:** We use the opentelemetry-instrumentation-langchain library. This automatically hooks into the LangGraph execution runtime.  
   * *Traces:* Every LLM call, tool execution, and state transition creates a "Span." These spans are linked to form a "Trace" representing the entire user session.  
   * *Metadata:* We attach metadata to spans, such as user\_id, session\_id, and model\_version.  
2. **Collector:** An OpenTelemetry Collector runs as a Docker container. It buffers the traces and metrics.  
3. **Storage & Visualization:**  
   * **Jaeger:** For visualizing the traces (waterfall view of agent reasoning).  
   * **Prometheus:** For storing aggregated time-series metrics.  
   * **Grafana:** For the operational dashboard.

### **7.2. Key Metrics for SLA and Accuracy**

**Table 3: Defined Metrics for Enterprise AI**

| Metric Category | Metric Name | Definition | Target (SLA) |
| :---- | :---- | :---- | :---- |
| **SLA / Latency** | **Time to First Token (TTFT)** | Time from user input to first character on screen. | \< 2.0 Seconds |
| **SLA / Latency** | **End-to-End Latency** | Time to complete a full multi-step workflow. | \< 10.0 Seconds (Simple) \< 60.0 Seconds (Complex) |
| **Accuracy** | **Tool Selection Rate** | % of times the Supervisor picks the correct tool (measured via implicit feedback). | \> 90% |
| **Accuracy** | **Hallucination Rate** | Estimated via a secondary "Evaluator" model checking RAG context consistency. | \< 5% |
| **Engagement** | **Session Length** | Number of turns per conversation. | N/A (Informational) |

**Implementation Snippet:**

Python

from opentelemetry import trace  
from openinference.instrumentation.langchain import LangChainInstrumentor

\# Initialize Tracer  
tracer \= trace.get\_tracer(\_\_name\_\_)

\# Auto-instrument LangGraph  
LangChainInstrumentor().instrument()

\# Custom Span for Business Logic  
with tracer.start\_as\_current\_span("erp\_lookup") as span:  
    span.set\_attribute("order.id", order\_id)  
    \#... execute logic...

## ---

**8\. User Interface: LangFlow and Frontend**

The requirement includes a "drag-and-drop UI." **LangFlow** is the optimal open-source solution for this, bridging the gap between developers and business analysts.31

### **8.1. LangFlow: The Builder UI**

LangFlow provides a visual canvas where users can drag components (Prompt, LLM, Tool, Vector Store) and connect them.

* **Role:** Rapid prototyping and flow modification.  
* **Integration:** We configure LangFlow to use the local vLLM endpoint as its "OpenAI" provider.  
* **Export:** Flows designed in LangFlow can be exported as JSON or Python code and loaded into the main LangGraph runtime for production deployment. This allows non-coders to tweak prompts or adjust RAG parameters without touching the core codebase.

### **8.2. Production Chat Interface**

For end-users, a custom React-based chat application is deployed.

* **Features:**  
  * **Streaming:** Connects to the LangGraph API via Server-Sent Events (SSE) to display text as it is generated.  
  * **Citations:** Renders references to RAG documents (e.g., "") allowing users to verify facts.33  
  * **Media:** Renders images generated by the ComfyUI agent inline within the chat bubble.  
  * **Feedback:** "Thumbs Up/Down" buttons on every message, which send data back to the Telemetry system for accuracy tracking.

## ---

**9\. Operational Scenarios and Agent Implementation**

To demonstrate the system's capability, we detail two specific agent workflows required by the prompt.

### **9.1. Scenario A: The "Order Exception" Handler**

**Objective:** A customer emails asking to modify an order that is already in progress.

**Agents Involved:** Email Agent, Supervisor, ERP Agent, MES Agent.

**Workflow Narrative:**

1. **Trigger:** The **Email Agent** ingests an email: *"Urgent: Please change the color of Order \#12345 to Red."*  
2. **Reasoning:** The **Supervisor** analyzes the intent ("Modify Order") and extracts entities ("Order \#12345", "Color: Red"). It delegates to the **ERP Agent**.  
3. **Data Retrieval:** The **ERP Agent** calls the Odoo MCP tool get\_order\_status(12345). The result is *"Status: Manufacturing"*.  
4. **Complex Decision:** The Supervisor's logic dictates: *"If status is Manufacturing, check physical progress via MES."* It delegates to the **MES Agent**.  
5. **IoT Query:** The **MES Agent** calls the OPC-UA MCP tool get\_job\_progress(12345). The result is *"Job is 60% complete. Paint stage finished."*  
6. **Resolution:** The Supervisor determines the modification is impossible (Paint is finished).  
7. **Response:** The Supervisor instructs the **Email Agent** to draft a reply: *"Dear Customer, Order \#12345 is 60% complete and past the painting stage. Modification is no longer possible."*  
8. **Safety:** The workflow pauses. A human manager logs into the UI, reviews the draft and the MES evidence, and clicks "Approve." The email is sent.

### **9.2. Scenario B: Visual Quality Inspection**

**Objective:** Analyze a photo of a manufactured part and log defects.

**Agents Involved:** Drag-and-Drop UI (Upload), Vision Agent, MES Agent.

**Workflow Narrative:**

1. **Trigger:** A shop floor operator uploads a photo of a gear via the Chat UI.  
2. **Analysis:** The **Supervisor** routes the image to the **Vision Agent** (running Qwen2.5-VL or similar).  
3. **Inference:** The Vision Agent analyzes the image against its prompt: *"Detect cracks or surface rust."* It identifies a hairline fracture.  
4. **Action:** The Supervisor routes to the **MES Agent** to log a "Quality Defect" ticket for the current batch.  
5. **Documentation:** The MES Agent calls mes\_mcp.log\_defect(batch\_id, type="crack", confidence=0.95).  
6. **Feedback:** The system responds to the operator: *"Defect logged. Batch \#998 placed on hold."*

## ---

**10\. Deployment Strategy**

The entire stack is containerized using Docker Compose for portability and ease of management on the Ubuntu host.

**Service Architecture:**

1. **vllm-server**: Hosts Qwen3-14b (GPU).  
2. **qdrant**: Vector Database (CPU/RAM).  
3. **postgres**: State persistence (CPU/SSD).  
4. **otel-collector**: Telemetry aggregation.  
5. **mcp-servers**: Lightweight containers for Odoo/Salesforce connectors.  
6. **comfyui**: Image generation (GPU).  
7. **langgraph-api**: The main application logic (Python/FastAPI).  
8. **langflow**: The Builder UI.

**Network Security:**

Since this is an "Edge" deployment, the Docker network is internal. Only the langgraph-api and langflow ports are exposed to the corporate intranet. All MCP traffic and database connections remain within the encrypted Docker network, ensuring that API keys for legacy apps are never exposed externally.

## **11\. Conclusion**

The architecture defined in this report transforms the **AMD Ryzen AI Max 395+** from a powerful laptop chip into a sovereign, enterprise-grade AI server. By carefully engineering the software stack—starting with the **ROCm 7.2** driver layer, optimizing **vLLM** for the unique memory topology of Strix Halo, and architecting a modular, agentic application with **LangGraph** and **MCP**—we achieve a system that satisfies the user's rigorous requirements for performance, privacy, and interoperability.

This is not a theoretical exercise; the 96GB unified memory of the Strix Halo enables a class of local AI applications that were previously impossible without rack-mounted server gear. The "Enterprise Autopilot" described here is capable of meaningful, autonomous work, bridging the gap between modern generative AI and the established systems of record that run the business.

#### **Works cited**

1. AMD Ryzen™ AI MAX+ 395 Processor: Breakthrough AI Performance in Thin and Light, accessed January 24, 2026, [https://www.amd.com/en/blogs/2025/amd-ryzen-ai-max-395-processor-breakthrough-ai-.html](https://www.amd.com/en/blogs/2025/amd-ryzen-ai-max-395-processor-breakthrough-ai-.html)  
2. Ubuntu native installation \- AMD ROCm documentation, accessed January 24, 2026, [https://rocm.docs.amd.com/projects/install-on-linux/en/latest/install/install-methods/package-manager/package-manager-ubuntu.html](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/install/install-methods/package-manager/package-manager-ubuntu.html)  
3. Linux support matrices by ROCm version — Use ROCm on Radeon and Ryzen, accessed January 24, 2026, [https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityryz/native\_linux/native\_linux\_compatibility.html](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html)  
4. AMD Updates ROCm to Support Ryzen AI Max and Radeon RX 9000 Series, accessed January 24, 2026, [https://www.techpowerup.com/forums/threads/amd-updates-rocm-to-support-ryzen-ai-max-and-radeon-rx-9000-series.337073/](https://www.techpowerup.com/forums/threads/amd-updates-rocm-to-support-ryzen-ai-max-and-radeon-rx-9000-series.337073/)  
5. Ubuntu 24.04: install rocm without amdgpu-dkms? \- Reddit, accessed January 24, 2026, [https://www.reddit.com/r/ROCm/comments/1chloqg/ubuntu\_2404\_install\_rocm\_without\_amdgpudkms/](https://www.reddit.com/r/ROCm/comments/1chloqg/ubuntu_2404_install_rocm_without_amdgpudkms/)  
6. Ubuntu AMDGPU installer installation \- AMD ROCm documentation, accessed January 24, 2026, [https://rocm.docs.amd.com/projects/install-on-linux/en/docs-6.4.0/install/install-methods/amdgpu-installer/amdgpu-installer-ubuntu.html](https://rocm.docs.amd.com/projects/install-on-linux/en/docs-6.4.0/install/install-methods/amdgpu-installer/amdgpu-installer-ubuntu.html)  
7. ROCm Device Support Wishlist \#4276 \- GitHub, accessed January 24, 2026, [https://github.com/ROCm/ROCm/discussions/4276](https://github.com/ROCm/ROCm/discussions/4276)  
8. Qwen/Qwen3-14B \- Hugging Face, accessed January 24, 2026, [https://huggingface.co/Qwen/Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B)  
9. Qwen3: Think Deeper, Act Faster | Qwen, accessed January 24, 2026, [https://qwenlm.github.io/blog/qwen3/](https://qwenlm.github.io/blog/qwen3/)  
10. \[HOW-TO\] Compiling VLLM from source on Strix Halo \- Framework Desktop, accessed January 24, 2026, [https://community.frame.work/t/how-to-compiling-vllm-from-source-on-strix-halo/77241](https://community.frame.work/t/how-to-compiling-vllm-from-source-on-strix-halo/77241)  
11. Running DeepSeek-OCR Locally on AMD Strix Halo: A Journey into Local AI-Powered Document Processing | by Yong Jie Wong \- Medium, accessed January 24, 2026, [https://medium.com/@yjwong/running-deepseek-ocr-locally-on-amd-strix-halo-a-journey-into-local-ai-powered-document-processing-ed9ab4c77ed0](https://medium.com/@yjwong/running-deepseek-ocr-locally-on-amd-strix-halo-a-journey-into-local-ai-powered-document-processing-ed9ab4c77ed0)  
12. AMD Strix Halo (Ryzen AI Max+ 395\) GPU LLM Performance : r/ROCm, accessed January 24, 2026, [https://www.reddit.com/r/ROCm/comments/1kn2sa0/amd\_strix\_halo\_ryzen\_ai\_max\_395\_gpu\_llm/](https://www.reddit.com/r/ROCm/comments/1kn2sa0/amd_strix_halo_ryzen_ai_max_395_gpu_llm/)  
13. ggml-org/llama.cpp: LLM inference in C/C++ \- GitHub, accessed January 24, 2026, [https://github.com/ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)  
14. von-development/awesome-LangGraph: An index of the LangChain \+ LangGraph ecosystem: concepts, projects, tools, templates, and guides for LLM & multi-agent apps. \- GitHub, accessed January 24, 2026, [https://github.com/von-development/awesome-LangGraph](https://github.com/von-development/awesome-LangGraph)  
15. LangGraph \- LangChain, accessed January 24, 2026, [https://www.langchain.com/langgraph](https://www.langchain.com/langgraph)  
16. Understanding the LangGraph Multi-Agent Supervisor | by akanshak \- Medium, accessed January 24, 2026, [https://medium.com/@akanshak/understanding-the-langgraph-multi-agent-supervisor-00fa1be4341b](https://medium.com/@akanshak/understanding-the-langgraph-multi-agent-supervisor-00fa1be4341b)  
17. langgraphjs/examples/multi\_agent/agent\_supervisor.ipynb at main \- GitHub, accessed January 24, 2026, [https://github.com/langchain-ai/langgraphjs/blob/main/examples/multi\_agent/agent\_supervisor.ipynb?ref=blog.langchain.com](https://github.com/langchain-ai/langgraphjs/blob/main/examples/multi_agent/agent_supervisor.ipynb?ref=blog.langchain.com)  
18. Model context protocol (MCP) for enterprise AI integration \- MicroStrategy, accessed January 24, 2026, [https://www.strategysoftware.com/blog/model-context-protocol-mcp-for-enterprise-ai-integration](https://www.strategysoftware.com/blog/model-context-protocol-mcp-for-enterprise-ai-integration)  
19. Model Context Protocol (MCP). MCP is an open protocol that… | by Aserdargun, accessed January 24, 2026, [https://medium.com/@aserdargun/model-context-protocol-mcp-e453b47cf254](https://medium.com/@aserdargun/model-context-protocol-mcp-e453b47cf254)  
20. AI Assistants Using LangGraph \- gettectonic.com, accessed January 24, 2026, [https://gettectonic.com/ai-assistants-using-langgraph/](https://gettectonic.com/ai-assistants-using-langgraph/)  
21. ISC-CodeConnect is a sophisticated multi-agent Retrieval-Augmented Generation (RAG) system specifically designed for Salesforce development. Built with LangGraph and powered by IBM WatsonX.ai Granite models, it orchestrates a network of specialized AI agents \- GitHub, accessed January 24, 2026, [https://github.com/KirtiJha/langgraph-salesforce-code-agent](https://github.com/KirtiJha/langgraph-salesforce-code-agent)  
22. A Digital Twin-Based Distributed Manufacturing Execution System for Industry 4.0 with AI-Powered On-The-Fly Replanning Capabilities \- MDPI, accessed January 24, 2026, [https://www.mdpi.com/2071-1050/15/7/6251](https://www.mdpi.com/2071-1050/15/7/6251)  
23. Manufacturing Execution Systems: The 300+ vendors looking to displace pen, paper, and spreadsheets in the factory \- IoT Analytics, accessed January 24, 2026, [https://iot-analytics.com/mes-vendors-replace-pen-paper-spreadsheets/](https://iot-analytics.com/mes-vendors-replace-pen-paper-spreadsheets/)  
24. Multi AI agents for customer support email automation built with Langchain & Langgraph \- GitHub, accessed January 24, 2026, [https://github.com/kaymen99/langgraph-email-automation](https://github.com/kaymen99/langgraph-email-automation)  
25. deimos-deimos/comfy\_api\_simplified: A simple way to schedule ComfyUI prompts with different parameters \- GitHub, accessed January 24, 2026, [https://github.com/deimos-deimos/comfy\_api\_simplified](https://github.com/deimos-deimos/comfy_api_simplified)  
26. How to Use ComfyUI API with Python: A Complete Guide | by Shawn Wong | Medium, accessed January 24, 2026, [https://medium.com/@next.trail.tech/how-to-use-comfyui-api-with-python-a-complete-guide-f786da157d37](https://medium.com/@next.trail.tech/how-to-use-comfyui-api-with-python-a-complete-guide-f786da157d37)  
27. AI Agents for Quality Control Defect Detection | Opsio Cloud, accessed January 24, 2026, [https://opsiocloud.com/knowledge-base/ai-agents-for-quality-control-and-defect-detection/](https://opsiocloud.com/knowledge-base/ai-agents-for-quality-control-and-defect-detection/)  
28. AI Visual Inspection System for Quality Control: Real Examples and What You Need to Know, accessed January 24, 2026, [https://dac.digital/ai-visual-inspection-system-for-quality-control/](https://dac.digital/ai-visual-inspection-system-for-quality-control/)  
29. Introducing End-to-End OpenTelemetry Support in LangSmith \- LangChain Blog, accessed January 24, 2026, [https://www.blog.langchain.com/end-to-end-opentelemetry-langsmith/](https://www.blog.langchain.com/end-to-end-opentelemetry-langsmith/)  
30. Tracing LangChain applications with OpenTelemetry \- New Relic, accessed January 24, 2026, [https://newrelic.com/blog/log/tracing-langchain-applications-with-opentelemetry](https://newrelic.com/blog/log/tracing-langchain-applications-with-opentelemetry)  
31. langflow-ai/langflow: Langflow is a powerful tool for ... \- GitHub, accessed January 24, 2026, [https://github.com/langflow-ai/langflow](https://github.com/langflow-ai/langflow)  
32. Langflow vs LangGraph: A Detailed Comparison for Building Agentic AI Systems \- ZenML, accessed January 24, 2026, [https://www.zenml.io/blog/langflow-vs-langgraph](https://www.zenml.io/blog/langflow-vs-langgraph)  
33. 42Q: AI Assistant Integration for Manufacturing Execution System (MES) \- ZenML LLMOps Database, accessed January 24, 2026, [https://www.zenml.io/llmops-database/ai-assistant-integration-for-manufacturing-execution-system-mes](https://www.zenml.io/llmops-database/ai-assistant-integration-for-manufacturing-execution-system-mes)