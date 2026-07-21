# AI provider catalog

Provider and model choices live in `config/ai-providers.json`. It contains no secrets. API keys stay in the private `.env.providers` file. KnowledgeForge loads both `.env` and `.env.providers`.

Included adapters:

- OpenAI
- Claude through Anthropic's native API
- local Ollama
- Google Gemini, Kimi, and DeepSeek through their OpenAI-compatible APIs

Copy `.env.providers.example` to `.env.providers`, add the matching key, restart once so the server reads the new environment, then select the provider and model in the interface:

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
MOONSHOT_API_KEY=
DEEPSEEK_API_KEY=
KF_OLLAMA_URL=http://127.0.0.1:11434
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

Then add `PROVIDER_API_KEY` to `.env` and restart KnowledgeForge. The existing provider dropdown discovers the entry automatically; no interface code change is required.
