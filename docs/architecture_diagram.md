```mermaid
graph TD
    %% Styling
    classDef client fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef gateway fill:#e0f2f1,stroke:#00695c,stroke-width:2px;
    classDef core fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    classDef ai fill:#f3e5f5,stroke:#4a148c,stroke-width:2px;
    classDef storage fill:#eceff1,stroke:#455a64,stroke-width:2px;

    %% Clients / Integrations
    subgraph Clients ["User Interfaces & Integrations"]
        Mobile[Mobile App]:::client
        Web[Web Dashboard]:::client
        Clawdbot[Clawdbot Personal Agent]:::client
        SlackUser[Slack User]:::client
        TeleUser[Telegram User]:::client
    end

    %% Gateways
    subgraph Gateways ["Integration Layer"]
        Copilot[CopilotKit Runtime]:::gateway
        S_Gateway[Slack Gateway]:::gateway
        T_Gateway[Telegram Gateway]:::gateway
        API_GW[Unified Tool Gateway]:::gateway
    end

    %% Core System
    subgraph Core ["BestBox Core"]
        Orchestrator[Agent Orchestrator<br/>(LangGraph)]:::core
        Router[Router Agent]:::core
        
        subgraph Agents
            ERP_A[ERP Agent]:::core
            CRM_A[CRM Agent]:::core
            Ops_A[IT Ops Agent]:::core
        end
    end

    %% AI Infrastructure
    subgraph AI ["AI Inference (ROCm)"]
        LLM[Qwen3-14B (vLLM)]:::ai
        Embed[BGE-M3 (TEI)]:::ai
        Rerank[BGE-Reranker (TEI)]:::ai
    end

    %% Data & Services
    subgraph Services ["Enterprise Data"]
        ERP[ERPNext]:::storage
        DB[(PostgreSQL)]:::storage
        VecDB[(Qdrant Vector DB)]:::storage
        KB[Knowledge Base files]:::storage
    end

    %% Relationships
    Web --> Copilot
    Mobile --> Copilot
    
    Clawdbot -- Skills/API --> API_GW
    
    SlackUser -- Messages --> S_Gateway
    TeleUser -- Messages --> T_Gateway
    
    Copilot --> Orchestrator
    S_Gateway --> Orchestrator
    T_Gateway --> Orchestrator
    API_GW --> Orchestrator

    Orchestrator --> Router
    Router --> ERP_A
    Router --> CRM_A
    Router --> Ops_A

    ERP_A --> LLM
    CRM_A --> LLM
    Ops_A --> LLM

    ERP_A --> ERP
    CRM_A --> DB
    
    %% RAG Flow
    Agents --> Embed
    Embed --> VecDB
    VecDB --> Rerank
    Rerank --> LLM
```
