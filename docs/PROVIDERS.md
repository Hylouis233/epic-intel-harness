# Model providers

The bundled baseline is deterministic and model-free. Optional adapters live outside the
candidate evaluation path:

- `ReplayProvider` resolves a canonical request hash to a checked fixture, enabling offline
  reproduction;
- `OpenAICompatibleProvider` performs an explicit HTTPS chat-completions request and records
  requested/resolved model IDs, token usage, latency, request hash, and response hash.

Provider failure raises `ProviderError`. The runtime must not silently replace a missing or
failed model with a fabricated success. Do not expose API keys in prompts, traces, fixtures,
artifacts, command arguments, or repository files; read them from the process environment in
a private adapter.

The public benchmark does not enable network access or instantiate a live provider. A future
model-backed candidate should be paired with a replay suite before results are treated as
reproducible.
