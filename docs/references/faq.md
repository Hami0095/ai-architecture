# FAQ & Troubleshooting

### Q: Why does CIRAS return "UNKNOWN" for some files?
**A**: CIRAS requires a complete call graph to certify a task as LOW risk. If your file uses heavy reflection, dynamic loading, or is outside the scanned source tree, CIRAS refuses to guess to preserve trust.

### Q: Can I use ArchAI with languages other than Python?
**A**: Currently, the `GraphEngine` is optimized for Python AST analysis. Basic file-level impact analysis works for all languages via Git churn, but symbol-level tracing is Python-specific for now.

### Q: How do I improve the 'Confidence Score' in my sprints?
**A**: SRC-RS typically lowers confidence for three reasons:
1. **Unresolved Dependencies**: Tasks are blocking each other.
2. **Missing Tests**: High-risk tasks lack historical test coverage evidence.
3. **Over-capacity**: Your team size and days are insufficient for the estimated effort.

### Q: My JSON output is malformed, what should I do?
**A**: Ensure you are using a modern LLM (like `glm-4.6` or `qwen2.5-coder`). If errors persist, try running with `--verbose` to see the raw LLM response.

### Q: Is there a way to exclude certain directories from the scan?
**A**: Yes. ArchAI automatically ignores `.git`, `node_modules`, and virtual environments. You can customize this in your `archai_config.yaml`.
