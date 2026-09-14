# Commit messages

Match the user's recent commit-message style when drafting or creating commits:

- Use a lowercase conventional prefix such as `fix:`, `perf:`, or `docs:`, followed by a concise imperative summary starting in lowercase.
- Follow the subject with a blank line and a flat list of `- ` bullets.
- Start each bullet with a lowercase imperative verb, preserve proper names and technical identifiers, and omit trailing periods.
- Describe concrete changes and their effects; scale the number of bullets to the diff.
- Inspect recent user-authored commits when needed to keep the style consistent. Do not copy older upstream commit conventions over the user's recent style.

This preference applies to commit-message generation as well as actual commits; a request for a message does not authorize creating a commit.
