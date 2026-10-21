# LocalGPT Plugins

This directory is reserved for LocalGPT plugin metadata; no plugin manifests are currently shipped.

Plugin folders are discovered through `plugin.json` manifests, but LocalGPT does not import or execute code from this directory. Runtime behavior is only available when the backend has a trusted handler for a known plugin id.

Current rules:

- plugins are disabled by default;
- `plugin.json` is metadata, permissions, and documentation links;
- unknown plugin ids may be detected, but they are not trusted;
- arbitrary Python, JavaScript, shell scripts, or binaries from plugin folders are not executed;
- dangerous actions such as running local commands, opening public access, or changing network settings require trusted backend code and explicit user confirmation.

No official plugin manifests are currently shipped. The registry remains a metadata-only extension point; any runtime behavior requires a separately reviewed backend-owned handler.
