If the user asks something like "what are my options?", "ready?",  "what can we work on", etc, present them with this list
    A - implement a feature
    B - fix a bug
    C - your choice

# Session workflow
The workflow you follow depends on their choice.

## If they choose implement a feature

1. We need a feature specification with a phased plan of PRs, with each PR composed of 1 or more atomic commits
    - Ask if they have a feature specification
    - If they answer yes, ask them to copy the text of the specificationi
    - If they say no, run the spec-collaborator agent
1. Iterate over each PR in the plane in order. If the PR has commits, iterate over each commit in order
    1. Explain the objective of the commit
    2. Create a list of test names in the given/when/then format. List only test names—no code.
    3. Create the tests.
    4. Analyze existing tests for conflicts and potential changes or deletions. 
	    1. If conflicts are found, list the conflicts, suggest changes, and ask for my input.
        - First need to design implementation and refine design
    5. Implement code changes that satisfy the commit objective. Run the tests you created in step 3. Iterate over code changes and tests until all tests are green. During this step, NEVER modify any test code.
    6. Run regression tests. If there are regressions, we will discuss a plan to address them.
        - If necessary, you will implement the plan to address regressions.
    7. Ask for my approval to commit the changes.
    8. Create a NEW PR ... ?? FORMAT ?? ... ?? AGENT ??

## If they choose to fix a bug

## Otherwise
