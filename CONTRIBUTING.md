# Contributing to KRL Tutorials

Thank you for your interest in contributing to KRL Tutorials! We welcome contributions from the community.

## How to Contribute

### Reporting Issues

If you find a bug, typo, or have a suggestion:

1. Check if the issue already exists in [GitHub Issues](https://github.com/the private source repository/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Your environment (OS, Python version, etc.)

### Suggesting New Tutorials

We're always looking to expand our tutorial library:

1. Open an issue with the "tutorial suggestion" label
2. Describe the topic, learning objectives, and target audience
3. Explain why this tutorial would be valuable
4. Include any relevant resources or references

### Submitting Changes

#### Pull Request Process

1. **Fork the repository** and create a new branch:
   ```bash
   git checkout -b feature/your-tutorial-name
   ```

2. **Make your changes**:
   - Follow the tutorial structure guidelines
   - Include clear code comments
   - Add exercises where appropriate
   - Test all code examples

3. **Commit your changes**:
   ```bash
   git commit -m "Add tutorial on [topic]"
   ```

4. **Push to your fork**:
   ```bash
   git push origin feature/your-tutorial-name
   ```

5. **Submit a pull request**:
   - Reference any related issues
   - Describe what the PR accomplishes
   - Include screenshots for visualization changes

#### Tutorial Structure

All tutorials should follow this format:

```markdown
# Tutorial Title

**Learning Objectives:**
- Objective 1
- Objective 2

**Prerequisites:**
- Required knowledge
- Required setup

**Estimated Time:** XX minutes

## Introduction
Brief overview of the topic

## Setup
Installation and configuration steps

## Core Concepts
Theory and explanations

## Hands-On Examples
Step-by-step code examples

## Exercises
Practice problems (with solutions in separate file)

## Summary
Key takeaways

## Further Reading
Additional resources
```

#### Code Style

- **Python**: Follow PEP 8 style guidelines
- **Comments**: Write clear, concise comments
- **Variables**: Use descriptive names
- **Functions**: Include docstrings
- **Notebooks**: Clear cell outputs for reference

#### Testing

Before submitting:

```bash
# Test notebook execution
jupyter nbconvert --to notebook --execute your_tutorial.ipynb

# Run tests
pytest tests/

# Check for security issues
pre-commit run --all-files
```

### Improving Existing Tutorials

Found a typo or want to improve an existing tutorial?

1. Make your changes
2. Test the notebook thoroughly
3. Submit a PR with a clear description

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers
- Accept constructive criticism
- Focus on what's best for the community
- Show empathy towards others

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Publishing others' private information
- Any conduct that could be considered unprofessional

## Questions?

- **Documentation**: https://github.com/KhipuResearch
- **Discussions**: https://github.com/orgs/KhipuResearch/discussions
- **Email**: contact@telosyn.co

## License

**This repository is proprietary.** See [LICENSE](LICENSE): the Software is the
exclusive property of Telosyn, Inc., licensed exclusively to Deloatch, Williams,
Faison & Parker, LLLP, and it may not be copied, modified, redistributed or used
to create derivative works without prior written consent.

By contributing, you agree that your contributions are licensed on those terms.

---

© 2026 Telosyn, Inc. All rights reserved.  
Khipu℠ is a service mark of Telosyn, Inc.
