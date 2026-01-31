# Security

- If any secrets are ever committed, **rotate them immediately** and treat them as compromised.
- This repository includes a pre-commit configuration (`.pre-commit-config.yaml`) and a GitHub Action (`.github/workflows/secret-scan.yml`) to detect secrets and fail CI on new leaks.
- To run the local pre-commit checks:

  ```bash
  pip install pre-commit
  pre-commit install
  pre-commit run --all-files
  ```

If you'd like, I can also add a pre-commit baseline (`.secrets.baseline`) and an automated workflow to update it when new, reviewed secrets are intentionally added (rarely needed).