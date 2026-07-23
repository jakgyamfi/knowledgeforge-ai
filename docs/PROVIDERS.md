# AI provider catalog

Provider and model choices live in `config/ai-providers.json`. It contains no secrets. Store API keys through the configured [secret-storage backend](SECRET-STORAGE.md).

Included adapters:

- Z.ai through its OpenAI-compatible API
- OpenAI
- Claude through Anthropic's native API
- xAI/Grok through its OpenAI-compatible API
- Meta through the first-party Llama API
- local Ollama
- Google Gemini, Kimi, and DeepSeek through their OpenAI-compatible APIs

The reviewed fallback model catalog is dated in `config/ai-providers.json`. After a provider key is configured, KnowledgeForge attempts to query that provider's model-list endpoint and uses the live compatible list. If discovery is unavailable, the reviewed fallback remains visible.

The July 22, 2026 review added Z.ai GLM-5.2, Gemini 3.1 Pro Preview, the current Claude family, xAI Grok 4.5, and Meta Llama 4 API models. Only language/chat models suitable for KnowledgeForge's analysis workflow belong in this catalog; image-only, audio-only, embedding, and deprecated models are intentionally omitted.

Store the required key, restart KnowledgeForge, then select the provider and model in the interface:

```powershell
knowledgeforge secrets set openai
knowledgeforge secrets list
```

## Add another compatible provider

Add an entry to `config/ai-providers.json`:

```json
{
  "id": "provider-id",
  "label": "Provider label",
  "adapter": "openai_compatible",
  "api_key_env": "PROVIDER_API_KEY",
  "base_url": "https://provider.example/v1",
  "models": ["model-name"]
}
```

Then run `knowledgeforge secrets set provider-id` and restart KnowledgeForge. The existing provider dropdown discovers the entry automatically; no interface code change is required.
