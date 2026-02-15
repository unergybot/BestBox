# Design: Configurable LLM Service in BestBox Admin

**Date:** 2026-02-14
**Status:** Approved
**Scope:** LLM inference service configuration only

## Overview

Enable BestBox administrators to configure LLM inference providers through the Admin UI, supporting:
- Local vLLM (default on-premise deployment)
- NVIDIA API (cloud inference via NVIDIA API catalog)
- OpenRouter (unified access to 100+ models)

Key requirements:
- Hot reload: configuration changes take effect immediately for new chat sessions without service restart
- Security: API keys encrypted at rest, with environment variable override support
- User experience: hybrid model selection (dropdown + custom input), connection testing, clear visual feedback

## Design Decisions

### Configuration Scope
**Decision:** Configure LLM inference service only (not embeddings, reranker, or speech services).

**Rationale:** Focused scope keeps initial implementation manageable. Future expansion to other services can follow the same pattern.

### Runtime Behavior
**Decision:** Hot reload - new chat sessions use updated configuration immediately without restarting Agent API service.

**Rationale:** Best user experience. Avoids downtime and service interruption. Active sessions continue with their original provider (session isolation).

### Provider Support
**Decision:** Support local vLLM, NVIDIA API, and OpenRouter initially.

**Rationale:**
- Local vLLM: existing default, required for on-premise deployments
- NVIDIA API: already integrated for LiveKit voice
- OpenRouter: provides access to many models (Claude, GPT-4, Gemini, Llama) through one API

### Model Selection
**Decision:** Hybrid approach - dropdown of common models per provider + "Custom" option for free text input.

**Rationale:** Provides easy selection for common models while remaining flexible for new/experimental models. Model list stored in database, updateable without code changes.

### UI Location
**Decision:** New Settings page at `/{locale}/admin/settings`.

**Rationale:** Most scalable approach. As BestBox grows, other system settings (API rate limits, SSO config, etc.) can be added to the same page. Avoids cluttering the System Status page.

### API Key Security
**Decision:** Encrypted storage in database with optional environment variable override.

**Rationale:**
- Encryption at rest protects API keys in database backups
- Environment variable override supports production deployments with external secret management (Vault, AWS Secrets Manager, etc.)
- UI convenience for development/testing, security for production

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Admin UI                             │
│           /{locale}/admin/settings                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Provider: [Local vLLM ▼]                         │   │
│  │ Model:    [qwen3-30b ▼]                          │   │
│  │ [Test Connection] [Save]                         │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────┘
                     │ POST /admin/settings/llm
                     ↓
┌─────────────────────────────────────────────────────────┐
│              LLMConfigService                           │
│  • Encrypt/decrypt API keys                             │
│  • Read/write configurations                            │
│  • Apply environment overrides                          │
│  • Fallback to env vars on DB error                     │
└────────────────────┬────────────────────────────────────┘
                     │ save_config()
                     ↓
┌─────────────────────────────────────────────────────────┐
│              PostgreSQL Database                        │
│  • llm_configurations (encrypted keys, audit trail)     │
│  • llm_provider_models (predefined model lists)         │
└────────────────────┬────────────────────────────────────┘
                     │ get_active_config()
                     ↓
┌─────────────────────────────────────────────────────────┐
│              LLMManager (Singleton)                     │
│  • Cache current LLM client                             │
│  • Detect config changes via hash comparison            │
│  • Create new client when config changes                │
│  • Thread-safe client access                            │
└────────────────────┬────────────────────────────────────┘
                     │ get_client()
                     ↓
┌─────────────────────────────────────────────────────────┐
│          agents/utils.py::get_llm()                     │
│  • Modified to call LLMManager.get_instance()           │
│  • Returns cached or refreshed ChatOpenAI client        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
              Agent execution
         (Router, ERP, CRM, IT Ops, OA)
```

## Database Schema

### Table: `llm_configurations`

Stores LLM provider configurations with encryption and audit trail.

```sql
CREATE TABLE llm_configurations (
    id SERIAL PRIMARY KEY,

    -- Provider config
    provider VARCHAR(50) NOT NULL,  -- 'local_vllm', 'nvidia', 'openrouter'
    is_active BOOLEAN NOT NULL DEFAULT false,  -- Only one config can be active

    -- Connection details
    base_url VARCHAR(500),  -- e.g., 'https://integrate.api.nvidia.com/v1'
    api_key_encrypted TEXT,  -- Fernet-encrypted, NULL for local_vllm
    model VARCHAR(200) NOT NULL,  -- e.g., 'qwen3-30b', 'minimaxai/minimax-m2'

    -- LLM parameters (stored as JSON for flexibility)
    parameters JSONB DEFAULT '{
        "temperature": 0.7,
        "max_tokens": 4096,
        "streaming": true,
        "max_retries": 2
    }'::jsonb,

    -- Audit trail
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),  -- username from JWT
    updated_by VARCHAR(100),

    -- Ensure only one active config
    CONSTRAINT only_one_active UNIQUE (is_active) WHERE (is_active = true)
);

-- Index for fast lookups
CREATE INDEX idx_llm_config_active ON llm_configurations(is_active) WHERE is_active = true;
```

**Key design points:**
- `is_active` with unique constraint ensures only one active configuration at a time
- `parameters` as JSONB allows flexibility for provider-specific options
- Audit fields (`created_by`, `updated_by`, timestamps) track configuration changes
- `api_key_encrypted` stores Fernet-encrypted API keys, NULL for local providers

### Table: `llm_provider_models`

Predefined model lists for dropdown UI.

```sql
CREATE TABLE llm_provider_models (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(200) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    is_recommended BOOLEAN DEFAULT false,
    sort_order INT DEFAULT 0,

    UNIQUE(provider, model_id)
);

-- Seed data for NVIDIA and OpenRouter
INSERT INTO llm_provider_models (provider, model_id, display_name, is_recommended, sort_order) VALUES
    -- Local vLLM
    ('local_vllm', 'qwen3-30b', 'Qwen3 30B (Local)', true, 1),

    -- NVIDIA API
    ('nvidia', 'minimaxai/minimax-m2', 'Minimax M2', true, 1),
    ('nvidia', 'meta/llama-3.1-nemotron-70b-instruct', 'Llama 3.1 Nemotron 70B', false, 2),
    ('nvidia', 'nvidia/llama-3.1-nemotron-ultra-253b', 'Nemotron Ultra 253B', false, 3),

    -- OpenRouter
    ('openrouter', 'anthropic/claude-3.5-sonnet', 'Claude 3.5 Sonnet', true, 1),
    ('openrouter', 'openai/gpt-4o', 'GPT-4o', false, 2),
    ('openrouter', 'google/gemini-pro-1.5', 'Gemini Pro 1.5', false, 3),
    ('openrouter', 'meta-llama/llama-3.3-70b-instruct', 'Llama 3.3 70B', false, 4);
```

**Key design points:**
- `is_recommended` flag highlights default choice per provider
- `sort_order` controls display order in dropdown
- Easy to add new models via SQL insert (no code changes)

## Backend Implementation

### Component 1: LLMConfigService

**File:** `services/llm_config_service.py`

**Responsibilities:**
- CRUD operations for LLM configurations
- API key encryption/decryption using Fernet
- Environment variable override logic
- Fallback to env vars when database unavailable

**Key Methods:**

```python
class LLMConfigService:
    def __init__(self, db_connection, encryption_key: str):
        """Initialize with database connection and Fernet encryption key."""
        self.db = db_connection
        self.fernet = Fernet(encryption_key.encode())

    def get_active_config(self) -> dict:
        """
        Get active LLM configuration with decrypted API key and env overrides.

        Precedence:
        1. Environment variables (if set)
        2. Database configuration
        3. Fallback to defaults on DB error
        """
        try:
            config = self._get_db_config()

            # Decrypt API key
            if config['api_key_encrypted']:
                config['api_key'] = self._decrypt_key(config['api_key_encrypted'])

            # Apply env overrides (env takes precedence)
            config = self._apply_env_overrides(config)

            return config

        except DatabaseError as e:
            logger.error(f"Database unavailable, falling back to env vars: {e}")
            return self._get_config_from_env()

    def save_config(self, provider: str, model: str, api_key: str,
                    base_url: str, parameters: dict, user: str) -> int:
        """
        Save new configuration (encrypts API key, deactivates old configs).

        Returns: ID of newly created configuration
        """
        # Encrypt API key if provided
        encrypted_key = self._encrypt_key(api_key) if api_key else None

        # Transaction:
        # 1. UPDATE llm_configurations SET is_active = false
        # 2. INSERT new config WITH is_active = true
        # 3. COMMIT

        return new_config_id

    def _apply_env_overrides(self, config: dict) -> dict:
        """Environment variables override database values for production."""
        provider = config['provider']

        # Override API keys
        if provider == 'nvidia' and os.getenv('NVIDIA_API_KEY'):
            config['api_key'] = os.getenv('NVIDIA_API_KEY')
        elif provider == 'openrouter' and os.getenv('OPENROUTER_API_KEY'):
            config['api_key'] = os.getenv('OPENROUTER_API_KEY')

        # Override base URL
        if os.getenv('LLM_BASE_URL'):
            config['base_url'] = os.getenv('LLM_BASE_URL')

        return config

    def _get_config_from_env(self) -> dict:
        """Fallback configuration from environment variables only."""
        return {
            'provider': 'local_vllm',
            'base_url': os.getenv('LLM_BASE_URL', 'http://localhost:8001/v1'),
            'model': os.getenv('LLM_MODEL', 'qwen3-30b'),
            'api_key': None,
            'parameters': {
                'temperature': 0.7,
                'max_tokens': 4096,
                'streaming': True,
                'max_retries': 2
            }
        }
```

**Error Handling:**
- Database connection failure → fallback to environment variables
- Missing encryption key → generate temporary key with warning in logs
- Invalid API key → validation on save, test connection endpoint

### Component 2: LLMManager

**File:** `services/llm_manager.py`

**Responsibilities:**
- Singleton pattern for global LLM client management
- Client caching to avoid recreating ChatOpenAI instances
- Config change detection via hash comparison
- Thread-safe client access

**Key Methods:**

```python
class LLMManager:
    """Singleton manager for LLM clients with caching and hot reload."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.config_service = get_llm_config_service()
        self.current_client = None
        self.current_config_hash = None
        self.client_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LLMManager()
        return cls._instance

    def get_client(self) -> ChatOpenAI:
        """
        Get LLM client, refreshing if configuration changed.

        Returns: Cached or newly created ChatOpenAI instance
        """
        with self.client_lock:
            # Get current config
            config = self.config_service.get_active_config()
            config_hash = self._hash_config(config)

            # Refresh client if config changed
            if config_hash != self.current_config_hash:
                logger.info(f"LLM config changed to {config['provider']}/{config['model']}, refreshing client...")
                self.current_client = self._create_client(config)
                self.current_config_hash = config_hash

            return self.current_client

    def _create_client(self, config: dict) -> ChatOpenAI:
        """Factory method to create ChatOpenAI instance from config."""
        try:
            return ChatOpenAI(
                base_url=config['base_url'],
                api_key=config.get('api_key', 'sk-no-key-required'),
                model=config['model'],
                temperature=config['parameters'].get('temperature', 0.7),
                max_tokens=config['parameters'].get('max_tokens', 4096),
                streaming=config['parameters'].get('streaming', True),
                max_retries=config['parameters'].get('max_retries', 2),
            )
        except Exception as e:
            logger.error(f"Failed to create LLM client: {e}")
            logger.info("Falling back to local vLLM")

            # Fallback to local vLLM on any error
            return ChatOpenAI(
                base_url='http://localhost:8001/v1',
                api_key='sk-no-key-required',
                model='qwen3-30b',
                temperature=0.7,
                max_tokens=4096,
                streaming=True
            )

    def force_refresh(self):
        """Force client refresh on next get_client() call (called from admin API after config save)."""
        with self.client_lock:
            self.current_config_hash = None

    def _hash_config(self, config: dict) -> str:
        """Generate hash of config for change detection."""
        import hashlib
        import json

        # Hash relevant fields only
        config_str = json.dumps({
            'provider': config['provider'],
            'base_url': config['base_url'],
            'model': config['model'],
            'api_key': config.get('api_key', ''),
            'parameters': config['parameters']
        }, sort_keys=True)

        return hashlib.sha256(config_str.encode()).hexdigest()
```

**Performance considerations:**
- Client caching prevents creating new ChatOpenAI instances on every agent request
- Hash comparison is fast (SHA-256 of ~200 bytes)
- Thread locks ensure safety under concurrent load

### Component 3: Modified agents/utils.py

**Change:** Replace environment variable based `get_llm()` with LLMManager call.

```python
# BEFORE (current implementation):
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8001/v1")

def get_llm(temperature: float = 0.7, max_tokens: int = 4096):
    return ChatOpenAI(
        base_url=LLM_BASE_URL,
        api_key="sk-no-key-required",
        model=os.environ.get("LLM_MODEL", "qwen3-30b"),
        temperature=temperature,
        streaming=True,
        max_retries=2,
        max_tokens=max_tokens,
    )

# AFTER (new implementation):
def get_llm(temperature: float = None, max_tokens: int = None):
    """
    Get LLM client from manager (respects active configuration).

    Args:
        temperature: Optional override for this call (defaults to config value)
        max_tokens: Optional override for this call (defaults to config value)

    Returns:
        ChatOpenAI instance configured per active LLM configuration
    """
    from services.llm_manager import LLMManager

    client = LLMManager.get_instance().get_client()

    # Allow per-call overrides of temperature/max_tokens
    if temperature is not None or max_tokens is not None:
        overrides = {}
        if temperature is not None:
            overrides['temperature'] = temperature
        if max_tokens is not None:
            overrides['max_tokens'] = max_tokens

        if overrides:
            client = client.bind(**overrides)

    return client
```

**Backward compatibility:** All existing agent code continues to work unchanged. Calls to `get_llm()` now dynamically use the active configuration.

### Component 4: Admin API Endpoints

**File:** `services/admin_endpoints.py`

**New endpoints:**

```python
@router.get("/settings/llm")
async def get_llm_config(user: Dict = Depends(require_permission("view"))):
    """Get active LLM configuration (API key masked for security)."""
    service = get_llm_config_service()
    config = service.get_active_config()

    # Mask API key in response
    if config.get('api_key'):
        key = config['api_key']
        config['api_key_masked'] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
        del config['api_key']

    # Check if env override is active
    config['env_override_active'] = _check_env_override(config['provider'])

    return config

@router.post("/settings/llm")
async def save_llm_config(
    request: LLMConfigRequest,
    user: Dict = Depends(require_permission("manage_settings"))
):
    """Save LLM configuration and trigger hot reload."""
    service = get_llm_config_service()

    config_id = service.save_config(
        provider=request.provider,
        model=request.model,
        api_key=request.api_key,
        base_url=request.base_url,
        parameters=request.parameters,
        user=user['username']
    )

    # Trigger hot reload
    from services.llm_manager import LLMManager
    LLMManager.get_instance().force_refresh()

    logger.info(f"LLM config updated by {user['username']}: {request.provider}/{request.model}")

    return {
        "success": True,
        "config_id": config_id,
        "message": "LLM configuration updated. New chat sessions will use this configuration."
    }

@router.get("/settings/llm/models/{provider}")
async def get_provider_models(
    provider: str,
    user: Dict = Depends(require_permission("view"))
):
    """Get available models for a provider from llm_provider_models table."""
    models = db.query(
        "SELECT model_id, display_name, description, is_recommended "
        "FROM llm_provider_models "
        "WHERE provider = %s "
        "ORDER BY sort_order ASC",
        (provider,)
    )

    return {"models": models}

@router.post("/settings/llm/test")
async def test_llm_connection(
    request: LLMConfigRequest,
    user: Dict = Depends(require_permission("view"))
):
    """Test LLM connection before saving configuration."""
    try:
        # Create temporary client
        test_client = ChatOpenAI(
            base_url=request.base_url,
            api_key=request.api_key,
            model=request.model,
            timeout=10
        )

        # Send test message
        response = test_client.invoke("Say 'connection successful' and nothing else.")

        return {
            "success": True,
            "message": "Connection successful",
            "response": response.content[:100]  # First 100 chars
        }

    except AuthenticationError:
        return {"success": False, "message": "Invalid API key"}
    except TimeoutError:
        return {"success": False, "message": "Connection timeout - check base URL and network"}
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}
```

**Pydantic models:**

```python
class LLMConfigRequest(BaseModel):
    provider: str  # 'local_vllm', 'nvidia', 'openrouter'
    base_url: str
    api_key: Optional[str] = None
    model: str
    parameters: Dict[str, Any] = {
        "temperature": 0.7,
        "max_tokens": 4096,
        "streaming": True,
        "max_retries": 2
    }
```

## Frontend Implementation

### New Page: Settings

**File:** `frontend/copilot-demo/app/[locale]/admin/settings/page.tsx`

**Layout:**
- Provider selection (radio buttons with descriptions)
- Provider-specific configuration panel (changes based on selected provider)
- Model selection (dropdown + custom input)
- API key input (password field with show/hide toggle)
- Environment override warning (when env var detected)
- Advanced parameters (collapsible section: temperature, max_tokens)
- Test Connection button
- Save Configuration button (with confirmation modal)

**Key Features:**

**1. Provider Selection UI:**
```tsx
<div className="space-y-3">
  <label className="text-sm font-medium">{t("provider")}</label>

  <div className="space-y-2">
    {/* Local vLLM */}
    <div className={`border rounded-lg p-4 cursor-pointer hover:bg-gray-50 ${
      provider === 'local_vllm' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
    }`} onClick={() => setProvider('local_vllm')}>
      <div className="flex items-start gap-3">
        <input type="radio" checked={provider === 'local_vllm'} readOnly />
        <div>
          <strong className="block">{t("providers.localVllm.name")}</strong>
          <span className="text-gray-500 text-sm">
            {t("providers.localVllm.description")}
          </span>
        </div>
      </div>
    </div>

    {/* Similar cards for NVIDIA and OpenRouter */}
  </div>
</div>
```

**2. Model Selection (Hybrid Dropdown):**
```tsx
const [models, setModels] = useState([]);
const [selectedModel, setSelectedModel] = useState('');
const [customModel, setCustomModel] = useState('');
const [showCustomInput, setShowCustomInput] = useState(false);

// Fetch models when provider changes
useEffect(() => {
  fetch(`/admin/settings/llm/models/${provider}`)
    .then(res => res.json())
    .then(data => setModels(data.models));
}, [provider]);

// UI
<div className="space-y-2">
  <label className="text-sm font-medium">{t("model")}</label>

  <select
    value={showCustomInput ? 'custom' : selectedModel}
    onChange={(e) => {
      if (e.target.value === 'custom') {
        setShowCustomInput(true);
      } else {
        setSelectedModel(e.target.value);
        setShowCustomInput(false);
      }
    }}
  >
    {models.map(m => (
      <option key={m.model_id} value={m.model_id}>
        {m.display_name} {m.is_recommended ? '(Recommended)' : ''}
      </option>
    ))}
    <option value="custom">{t("customModel")}</option>
  </select>

  {showCustomInput && (
    <input
      type="text"
      placeholder={t("enterModelName")}
      value={customModel}
      onChange={(e) => setCustomModel(e.target.value)}
      className="mt-2"
    />
  )}
</div>
```

**3. API Key Input with Environment Override Detection:**
```tsx
const [envOverride, setEnvOverride] = useState(false);

useEffect(() => {
  // Check if env override is active for this provider
  fetch('/admin/settings/llm')
    .then(res => res.json())
    .then(data => setEnvOverride(data.env_override_active));
}, [provider]);

// UI
{envOverride ? (
  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
    <div className="flex items-center gap-2 text-blue-700 text-sm">
      <InfoIcon className="w-4 h-4" />
      <span>{t("envOverrideActive")}</span>
    </div>
    <code className="text-xs block mt-1 text-blue-600">
      {t("usingEnvVar", { var: `${provider.toUpperCase()}_API_KEY` })}
    </code>
  </div>
) : (
  <div className="relative">
    <input
      type={showApiKey ? "text" : "password"}
      value={apiKey}
      onChange={(e) => setApiKey(e.target.value)}
      placeholder="sk-..."
    />
    <button onClick={() => setShowApiKey(!showApiKey)}>
      {showApiKey ? t("hide") : t("show")}
    </button>
  </div>
)}
```

**4. Test Connection:**
```tsx
const handleTestConnection = async () => {
  setTesting(true);
  setTestResult(null);

  try {
    const res = await fetch('/admin/settings/llm/test', {
      method: 'POST',
      body: JSON.stringify({
        provider,
        base_url: baseUrl,
        api_key: apiKey,
        model: showCustomInput ? customModel : selectedModel
      })
    });

    const data = await res.json();
    setTestResult(data);
  } finally {
    setTesting(false);
  }
};

// UI
<button onClick={handleTestConnection} disabled={testing}>
  {testing ? <Spinner /> : <TestIcon />}
  {testing ? t("testing") : t("testConnection")}
</button>

{testResult && (
  <div className={testResult.success ? "alert-success" : "alert-error"}>
    {testResult.message}
  </div>
)}
```

**5. Save with Confirmation:**
```tsx
const handleSave = async () => {
  const confirmed = await showConfirmModal({
    title: t("confirmUpdate"),
    message: t("confirmUpdateMessage"),
    confirmText: t("update")
  });

  if (!confirmed) return;

  setSaving(true);

  try {
    const res = await fetch('/admin/settings/llm', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        provider,
        base_url: baseUrl,
        api_key: apiKey,
        model: showCustomInput ? customModel : selectedModel,
        parameters: {
          temperature,
          max_tokens: maxTokens,
          streaming: true,
          max_retries: 2
        }
      })
    });

    if (res.ok) {
      showToast(t("configUpdated"), "success");
    }
  } finally {
    setSaving(false);
  }
};
```

### Navigation Update

**File:** `frontend/copilot-demo/app/[locale]/admin/AdminSidebar.tsx`

Add Settings to the navigation menu:

```tsx
const menuItems = [
  { href: "/admin", icon: LayoutDashboard, label: t("dashboard") },
  { href: "/admin/documents", icon: FileText, label: t("documents") },
  { href: "/admin/kb", icon: Database, label: t("knowledgeBase") },
  { href: "/admin/users", icon: Users, label: t("users") },
  { href: "/admin/system", icon: Activity, label: t("system") },
  { href: "/admin/settings", icon: Settings, label: t("settings") }, // NEW
];
```

### Internationalization

**Files:** `frontend/copilot-demo/messages/en.json`, `messages/zh.json`

Add translations under `AdminNew.settings` namespace:

```json
{
  "AdminNew": {
    "settings": {
      "title": "Settings",
      "subtitle": "Configure system-wide settings",

      "llmConfig": "LLM Configuration",
      "provider": "Provider",
      "model": "Model",
      "apiKey": "API Key",
      "customModel": "Custom model...",
      "enterModelName": "Enter model name",

      "providers": {
        "localVllm": {
          "name": "Local vLLM",
          "description": "Run models on your own hardware (AMD ROCm / NVIDIA CUDA)"
        },
        "nvidia": {
          "name": "NVIDIA API",
          "description": "Cloud inference via NVIDIA's API catalog"
        },
        "openrouter": {
          "name": "OpenRouter",
          "description": "Access 100+ models through unified API"
        }
      },

      "envOverrideActive": "Environment variable override active",
      "usingEnvVar": "Using {var} from .env",

      "testConnection": "Test Connection",
      "testing": "Testing...",
      "saveConfiguration": "Save Configuration",
      "saving": "Saving...",

      "confirmUpdate": "Update LLM Configuration?",
      "confirmUpdateMessage": "New chat sessions will use this configuration immediately. Active sessions will continue with their current provider.",
      "update": "Update Configuration",

      "configUpdated": "LLM configuration updated successfully",

      "advancedParameters": "Advanced Parameters",
      "temperature": "Temperature",
      "maxTokens": "Max Tokens"
    }
  }
}
```

## Data Flow

### Configuration Change Flow

```
1. User clicks "Save Configuration" in Admin UI
         ↓
2. Frontend shows confirmation modal
         ↓
3. User confirms → POST /admin/settings/llm
         ↓
4. LLMConfigService.save_config()
    → Encrypt API key with Fernet
    → Begin database transaction
    → UPDATE llm_configurations SET is_active = false (all rows)
    → INSERT new configuration WITH is_active = true
    → Commit transaction
    → Return new config ID
         ↓
5. API endpoint calls LLMManager.force_refresh()
    → Sets current_config_hash = None
         ↓
6. API returns success response
         ↓
7. Frontend shows success toast
         ↓
8. Next chat request arrives
         ↓
9. Agent calls get_llm()
    → LLMManager.get_client()
    → Reads active config from database
    → Applies environment overrides
    → Hashes config
    → Compares hash with current_config_hash (None → mismatch)
    → Creates new ChatOpenAI instance
    → Caches client and hash
    → Returns new client
         ↓
10. Agent uses new LLM provider for inference
```

### Chat Request Flow (Hot Reload)

```
User sends chat message
         ↓
CopilotKit API → /v1/chat/completions
         ↓
Router agent initialization
         ↓
get_llm() called
         ↓
LLMManager.get_client()
    → Read active config from llm_configurations WHERE is_active = true
    → Apply environment variable overrides:
        - NVIDIA_API_KEY → config['api_key']
        - LLM_BASE_URL → config['base_url']
    → Generate config hash (SHA-256 of provider+model+url+key+params)
    → Compare with current_config_hash

    IF hash matches:
        → Return cached client (fast path, ~0.1ms)

    ELSE (config changed):
        → Log: "LLM config changed, refreshing client..."
        → Create new ChatOpenAI instance
        → Update current_client and current_config_hash
        → Return new client (slow path, ~50ms)
         ↓
Agent executes with client
         ↓
Response streamed to user
```

## Security

### Encryption

**Encryption Key Management:**
- Use Fernet symmetric encryption (cryptography library)
- Master key stored in `ENCRYPTION_KEY` environment variable
- Key generation: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Add to `.env.example`: `ENCRYPTION_KEY=your-32-byte-fernet-key-here`

**Encryption implementation:**
```python
from cryptography.fernet import Fernet

def _encrypt_key(self, api_key: str) -> str:
    """Encrypt API key for storage."""
    return self.fernet.encrypt(api_key.encode()).decode()

def _decrypt_key(self, encrypted_key: str) -> str:
    """Decrypt API key from storage."""
    return self.fernet.decrypt(encrypted_key.encode()).decode()
```

**Fallback behavior:**
- If `ENCRYPTION_KEY` not set: generate temporary key + warning in logs
- Production deployments MUST set `ENCRYPTION_KEY` for persistent decryption

### API Key Protection

**In API responses:**
- Never return raw API keys in GET endpoints
- Mask keys: `sk-12345678...abcd` (first 8 + last 4 characters)
- Omit `api_key` field entirely, provide `api_key_masked` instead

**In logs:**
```python
def _mask_api_key(key: str) -> str:
    """Mask API key for logging."""
    if not key or len(key) < 12:
        return "***"
    return f"{key[:8]}...{key[-4:]}"

logger.info(f"Using API key: {_mask_api_key(config['api_key'])}")
```

**In database:**
- Store only encrypted values in `api_key_encrypted` column
- Never log decrypted keys
- Decrypt only when needed (during client creation)

### Environment Variable Precedence

**Security model:**
- Environment variables OVERRIDE database values
- Production deployments can set `NVIDIA_API_KEY`, `OPENROUTER_API_KEY` in env
- Admin UI shows warning when env override is active
- This allows external secret management (Vault, AWS Secrets Manager) without storing keys in database

**UI indication:**
```tsx
{envOverride && (
  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
    <InfoIcon /> Environment variable override active
    <code>Using NVIDIA_API_KEY from .env</code>
  </div>
)}
```

### RBAC

**Permissions:**
- `view` - View LLM configuration (API keys masked)
- `manage_settings` - Update LLM configuration

**Endpoint protection:**
```python
@router.get("/settings/llm")
async def get_llm_config(user: Dict = Depends(require_permission("view"))):
    ...

@router.post("/settings/llm")
async def save_llm_config(user: Dict = Depends(require_permission("manage_settings"))):
    ...
```

**Role assignment:**
- `admin` role: has `manage_settings` permission
- `engineer` role: has `view` permission only
- `viewer` role: no access to settings

## Error Handling

### Database Failures

**Scenario:** PostgreSQL unavailable during config read

**Behavior:**
```python
def get_active_config(self) -> dict:
    try:
        config = self._get_db_config()
    except DatabaseError as e:
        logger.error(f"Database unavailable, falling back to env vars: {e}")
        return self._get_config_from_env()
```

**Fallback config:**
- Provider: `local_vllm`
- Base URL: `LLM_BASE_URL` env var or `http://localhost:8001/v1`
- Model: `LLM_MODEL` env var or `qwen3-30b`
- No API key (local doesn't need one)

**Impact:** Agents continue to work with local vLLM even if database is down.

### No Active Configuration

**Scenario:** No rows in `llm_configurations` with `is_active = true`

**Behavior:**
```python
def _get_db_config(self) -> dict:
    config = db.query("SELECT * FROM llm_configurations WHERE is_active = true")

    if not config:
        logger.warning("No active LLM config found, creating default")
        self._create_default_config()
        config = db.query("SELECT * FROM llm_configurations WHERE is_active = true")

    return config

def _create_default_config(self):
    """Auto-create default local vLLM configuration."""
    db.execute(
        "INSERT INTO llm_configurations (provider, is_active, base_url, model, created_by) "
        "VALUES ('local_vllm', true, 'http://localhost:8001/v1', 'qwen3-30b', 'system')"
    )
```

**Impact:** System self-heals by creating default config.

### Invalid API Key

**Scenario:** User enters invalid API key and tries to save

**Mitigation:**
- "Test Connection" button (recommended before save)
- Test endpoint validates credentials before saving
- If user saves without testing, first inference will fail with clear error

**Test connection implementation:**
```python
@router.post("/settings/llm/test")
async def test_llm_connection(request: LLMConfigRequest):
    try:
        client = ChatOpenAI(...)
        response = client.invoke("Say 'test successful' and nothing else.")
        return {"success": True, "message": "Connection successful"}
    except AuthenticationError:
        return {"success": False, "message": "Invalid API key"}
```

### Client Creation Failure

**Scenario:** ChatOpenAI initialization fails (e.g., network error, invalid base URL)

**Behavior:**
```python
def _create_client(self, config: dict) -> ChatOpenAI:
    try:
        return ChatOpenAI(...)
    except Exception as e:
        logger.error(f"Failed to create LLM client: {e}")
        logger.info("Falling back to local vLLM")

        return ChatOpenAI(
            base_url='http://localhost:8001/v1',
            api_key='sk-no-key-required',
            model='qwen3-30b',
            ...
        )
```

**Impact:** System always has a working LLM client (local vLLM fallback).

### Concurrent Config Changes

**Scenario:** Admin A and Admin B both save LLM config simultaneously

**Protection:**
- Database transaction with `is_active` unique constraint
- Only one config can be `is_active = true` at a time
- Second transaction will succeed (overwrites first)
- LLMManager's `client_lock` ensures thread-safe client refresh

**No data loss:** Audit trail preserves both configs with `created_by` and timestamps.

## Testing Strategy

### Unit Tests

**LLMConfigService:**
- `test_encrypt_decrypt_api_key()` - Round-trip encryption
- `test_env_override_takes_precedence()` - Environment variables win
- `test_fallback_to_env_on_db_error()` - Database failure fallback
- `test_save_config_deactivates_old()` - Transaction integrity
- `test_create_default_config()` - Auto-initialization

**LLMManager:**
- `test_singleton_pattern()` - Only one instance
- `test_client_caching()` - Same instance when config unchanged
- `test_client_refresh_on_config_change()` - New instance when config changes
- `test_force_refresh()` - Manual cache invalidation
- `test_thread_safety()` - Concurrent access from multiple threads

**Admin API:**
- `test_get_llm_config_masks_api_key()` - Security: keys masked
- `test_save_llm_config_requires_permission()` - RBAC enforcement
- `test_test_connection_detects_invalid_key()` - Validation
- `test_get_provider_models()` - Model list retrieval

### Integration Tests

**End-to-end configuration change:**
```python
def test_e2e_config_change_flow():
    # 1. Initial state: local vLLM
    client1 = get_llm()
    assert 'localhost:8001' in client1.base_url

    # 2. Admin saves NVIDIA config via API
    response = admin_client.post("/admin/settings/llm", json={...})
    assert response.status_code == 200

    # 3. New client uses NVIDIA
    client2 = get_llm()
    assert 'nvidia.com' in client2.base_url

    # 4. Send chat message, verify it works
    chat = user_client.post("/v1/chat/completions", json={...})
    assert chat.status_code == 200
```

**Active session isolation:**
```python
def test_active_session_unaffected_by_config_change():
    # Start session with local vLLM
    session1 = create_chat_session()
    msg1 = session1.send("Hello")
    assert msg1.used_provider == "local_vllm"

    # Change to NVIDIA
    change_llm_config("nvidia")

    # Session 1 continues with vLLM
    msg2 = session1.send("Continue")
    assert msg2.used_provider == "local_vllm"

    # New session uses NVIDIA
    session2 = create_chat_session()
    msg3 = session2.send("Hello")
    assert msg3.used_provider == "nvidia"
```

### Performance Tests

**Client caching effectiveness:**
```python
def test_client_creation_performance():
    manager = LLMManager.get_instance()

    # 1000 calls should be fast due to caching
    start = time.time()
    for _ in range(1000):
        client = manager.get_client()
    duration = time.time() - start

    assert duration < 0.1  # < 100ms for 1000 calls
```

**Concurrent request handling:**
```python
def test_concurrent_requests_with_config_change():
    # 50 concurrent chat requests while config changes mid-flight
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(send_chat) for _ in range(50)]

        # Change config while requests in flight
        time.sleep(0.5)
        change_llm_config("nvidia")

        results = [f.result() for f in futures]

    # All should succeed (no race conditions)
    assert all(r.status_code == 200 for r in results)
```

### Manual Testing Checklist

**Pre-release validation:**
- [ ] Fresh database migration executes successfully
- [ ] Default local vLLM config is auto-created
- [ ] `ENCRYPTION_KEY` generation documented in setup guide
- [ ] Settings page loads in EN and ZH locales
- [ ] Provider switching works: Local → NVIDIA → OpenRouter → Local
- [ ] Model dropdown populates correctly per provider
- [ ] Custom model input works
- [ ] "Test Connection" button validates credentials
- [ ] API key masking displays correctly (`sk-****...abcd`)
- [ ] Environment override warning shows when `NVIDIA_API_KEY` set in `.env`
- [ ] Save confirmation modal appears
- [ ] Hot reload: save config → new chat uses new provider
- [ ] Active session isolation: ongoing chat unaffected by config change
- [ ] Permission enforcement: viewer cannot save
- [ ] Error handling: invalid API key shows error
- [ ] Fallback: stop PostgreSQL → system uses env vars
- [ ] Logs: no raw API keys visible

## Migration & Deployment

### Database Migration

**File:** `migrations/006_llm_config.sql`

```sql
-- LLM configuration tables
CREATE TABLE llm_configurations (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    base_url VARCHAR(500),
    api_key_encrypted TEXT,
    model VARCHAR(200) NOT NULL,
    parameters JSONB DEFAULT '{
        "temperature": 0.7,
        "max_tokens": 4096,
        "streaming": true,
        "max_retries": 2
    }'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    CONSTRAINT only_one_active UNIQUE (is_active) WHERE (is_active = true)
);

CREATE INDEX idx_llm_config_active ON llm_configurations(is_active) WHERE is_active = true;

CREATE TABLE llm_provider_models (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(200) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    is_recommended BOOLEAN DEFAULT false,
    sort_order INT DEFAULT 0,
    UNIQUE(provider, model_id)
);

-- Seed default configuration (local vLLM)
INSERT INTO llm_configurations
    (provider, is_active, base_url, model, created_by)
VALUES
    ('local_vllm', true, 'http://localhost:8001/v1', 'qwen3-30b', 'system');

-- Seed provider models
INSERT INTO llm_provider_models (provider, model_id, display_name, is_recommended, sort_order) VALUES
    ('local_vllm', 'qwen3-30b', 'Qwen3 30B (Local)', true, 1),
    ('nvidia', 'minimaxai/minimax-m2', 'Minimax M2', true, 1),
    ('nvidia', 'meta/llama-3.1-nemotron-70b-instruct', 'Llama 3.1 Nemotron 70B', false, 2),
    ('nvidia', 'nvidia/llama-3.1-nemotron-ultra-253b', 'Nemotron Ultra 253B', false, 3),
    ('openrouter', 'anthropic/claude-3.5-sonnet', 'Claude 3.5 Sonnet', true, 1),
    ('openrouter', 'openai/gpt-4o', 'GPT-4o', false, 2),
    ('openrouter', 'google/gemini-pro-1.5', 'Gemini Pro 1.5', false, 3),
    ('openrouter', 'meta-llama/llama-3.3-70b-instruct', 'Llama 3.3 70B', false, 4);

-- RBAC: Add manage_settings permission
INSERT INTO permissions (name, description) VALUES
    ('manage_settings', 'Modify system settings including LLM configuration')
ON CONFLICT (name) DO NOTHING;

-- Grant to admin role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'admin' AND p.name = 'manage_settings'
ON CONFLICT DO NOTHING;
```

### Environment Setup

**Add to `.env.example`:**
```bash
# LLM Service Configuration
# These environment variables OVERRIDE database settings
ENCRYPTION_KEY=  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Optional: Override LLM provider settings (takes precedence over database)
#LLM_BASE_URL=http://localhost:8001/v1
#LLM_MODEL=qwen3-30b
#NVIDIA_API_KEY=
#OPENROUTER_API_KEY=
```

### Deployment Steps

**For new installations:**
1. Run migration: `psql < migrations/006_llm_config.sql`
2. Generate encryption key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. Add to `.env`: `ENCRYPTION_KEY=<generated-key>`
4. Restart Agent API: `./scripts/start-agent-api.sh`
5. Frontend: No changes needed (hot reload picks up new Settings page)

**For existing deployments:**
1. Backup database: `pg_dump bestbox > backup.sql`
2. Run migration (creates default local vLLM config)
3. Generate and set `ENCRYPTION_KEY`
4. Restart Agent API
5. Verify: Navigate to `/{locale}/admin/settings`, confirm local vLLM is active

**Rollback plan:**
```sql
-- If migration fails, rollback:
DROP TABLE IF EXISTS llm_configurations CASCADE;
DROP TABLE IF EXISTS llm_provider_models CASCADE;
DELETE FROM permissions WHERE name = 'manage_settings';

-- Restore from backup if needed:
psql bestbox < backup.sql
```

### Startup Validation

**Add to `services/agent_api.py`:**
```python
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Agent API...")

    # Initialize LLM Manager
    try:
        from services.llm_manager import LLMManager
        manager = LLMManager.get_instance()
        client = manager.get_client()

        config = manager.config_service.get_active_config()
        logger.info(f"✅ LLM Manager initialized: {config['provider']}/{config['model']}")

        if config.get('api_key'):
            logger.info(f"   API key: {_mask_key(config['api_key'])}")
        logger.info(f"   Base URL: {config['base_url']}")

    except Exception as e:
        logger.error(f"❌ LLM Manager initialization failed: {e}")
        logger.warning("   System will use fallback configuration")
        logger.warning("   Check database connection and ENCRYPTION_KEY")
```

## Future Enhancements

### Phase 2 (not in this design):

**Per-agent LLM configuration:**
- Router uses fast/cheap model (GPT-4o-mini)
- ERP agent uses expensive/accurate model (GPT-4o, Claude Opus)
- Requires: `agent_type` column in `llm_configurations`, modified `get_llm(agent_type)`

**Cost tracking:**
- Log token usage per provider
- Display monthly cost estimates in admin UI
- Alerts when approaching budget limits

**Automatic fallback:**
- Primary: NVIDIA API
- Fallback: OpenRouter
- Last resort: Local vLLM
- Trigger: API rate limit, authentication error, timeout

**Model performance comparison:**
- A/B test different models
- Track response quality metrics (latency, user feedback)
- Recommend best model per domain

**Custom provider templates:**
- User defines new provider: Groq, Together AI, DeepSeek
- Admin UI: "Add Custom Provider" with base URL template
- Stored in `llm_provider_templates` table

## Summary

This design enables flexible LLM provider configuration through the BestBox Admin UI with:

**Key Features:**
- Hot reload: no service restart needed
- Security: encrypted API keys with env override
- User experience: test connection before save, clear feedback
- Production-ready: fallbacks, audit trail, RBAC

**Architectural Highlights:**
- Configuration Service pattern for clean separation
- LLM Manager singleton with client caching
- Thread-safe concurrent access
- Environment variable precedence for production deployments

**Success Criteria:**
- Admin can switch from local vLLM to NVIDIA API in < 30 seconds
- New chat sessions use updated config immediately
- Active sessions unaffected by config changes
- All API keys encrypted at rest
- Zero downtime during configuration changes

**Implementation Effort:**
- Backend: ~500-700 lines (LLMConfigService, LLMManager, API endpoints)
- Frontend: ~400-500 lines (Settings page, translations)
- Database: 2 tables + migration script
- Testing: ~15-20 test cases
- Total: 2-3 developer days

**Risks & Mitigations:**
- Risk: Database failure → Mitigation: fallback to env vars
- Risk: Invalid API key → Mitigation: test connection endpoint
- Risk: Concurrent config changes → Mitigation: database constraints + locks
- Risk: Missing encryption key → Mitigation: auto-generate temporary + warning
