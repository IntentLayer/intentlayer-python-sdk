# Contributing to IntentLayer Python SDK

Thanks for taking the time to contribute 🎉 — whether you’re fixing a typo, adding docs, or implementing a new feature, we welcome your help!

> **Before you start:** By participating in this project, you agree to follow our [Code of Conduct](./CODE_OF_CONDUCT.md).

---

## 1. Getting Started

### 1.1 Fork & Clone

```bash
git clone git@github.com:<your‑github‑handle>/intentlayer-python-sdk.git
cd intentlayer-python-sdk
git remote add upstream https://github.com/IntentLayer/intentlayer-python-sdk.git
```

### 1.2 Install Dev Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 1.3 Run the Test Suite

```bash
pytest --cov=intentlayer_sdk --cov-report=term-missing
```
> PRs must keep coverage **≥ 90 %**.

---

## 2. Making Changes

1. **Create a branch** off of `main`:
   ```bash
   git checkout -b feat/<short-description>
   ```
2. **Write or update tests** to cover your change.
3. **Format & type‑check**:
   ```bash
   black .
   isort .
   mypy intentlayer_sdk
   ```
4. **Commit** using conventional commit messages (`feat:`, `fix:`, `docs:` etc.).
5. **Push** and open a Pull Request against `IntentLayer/intentlayer-python-sdk`.

---

## 3. Pull Request Checklist

- ✅ Tests pass (`pytest`) and coverage ≥ 90 %.
- ✅ `black` shows no changes.
- ✅ `mypy` reports no new type errors.
- ✅ `CHANGELOG.md` updated (if user‑visible change).
- ✅ Docs / README updated if behavior changes.
- ✅ No secrets or private keys committed.

---

## 4. Issue Guidelines

- Search existing issues before opening a new one.
- Include **steps to reproduce** and **expected vs. actual behavior**.
- Use labels: `bug`, `enhancement`, `question`, `docs`.

---

## 5. Local Testing with Sepolia

- You’ll need a Sepolia private key and some test ETH; see the README’s *Security Considerations*.
- The default `pytest` configuration uses mocked Web3 and respx, so no on‑chain calls run during CI.

---

## 6. Release Process (maintainers only)

1. Bump version in `pyproject.toml`.
2. Commit with `chore(release): vX.Y.Z`.
3. Tag and push: `git tag vX.Y.Z && git push --tags`.
4. GitHub Action publishes the package to PyPI and creates a GitHub release.

---

### Thank you for helping make IntentLayer better!  
Need help? Ping us in Discussions or email **dev@intentlayer.net**.

