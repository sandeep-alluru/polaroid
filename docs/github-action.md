# GitHub Action

Use polaroid directly in your GitHub Actions workflow:

```yaml
- name: polaroid
  uses: sandeep-alluru/polaroid@v0.1.0
  with:
    # TODO: add action inputs
    fail-on-error: "true"
```

Or use the CLI directly:

```yaml
- name: Install polaroid
  run: pip install polaroid

- name: Run polaroid
  run: polaroid --help
```
