# GitHub Action

Use scenemem directly in your GitHub Actions workflow:

```yaml
- name: scenemem
  uses: sandeep-alluru/scenemem@v0.1.0
  with:
    # TODO: add action inputs
    fail-on-error: "true"
```

Or use the CLI directly:

```yaml
- name: Install scenemem
  run: pip install scenemem

- name: Run scenemem
  run: scenemem --help
```
