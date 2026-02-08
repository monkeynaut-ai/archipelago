---
allowed-tools: Bash(git checkout:*), Bash(git commit:*), Bash(npm test:*), Bash(npx tap:*), Bash(npm install), Bash(gh issue view:*), Bash(git add:*), Edit(./**/*)
description: fix the specified github issue
argument-hint: [issueId]
---

Your task is to fix github issue #$1. Fix this issue by following this process

- before starting work, verify that all tests pass. If they do not, summarize the tests that are failing and then exit
- fetch the github issue
    - If you cannot fetch the issue, warn the user and then exit
- analyze the issue to understand how to reproduce the problem
    - If you cannot reproduce the problem, explain why and then exit
- plan the creation of tests that reproduce the problem. The intent is to create tests that fail initially, as described and discussed in the github issue. Later in the process the goal will be to fix issue and then have these tests pass
- checkout a branch named fix/gh-issue-<issueId>
- create the tests. Verify that they fail. If they do not fail, modify the tests to capture the reported problem. During this phase you must not modify any source code and you must not modify any existing tests.
- when you are satisfied that the tests capture the problem that will be fixed, commit the changes with an appropriate message
- estimate the complexity of the problem.
- if the problem is moderately complex or complex, use deep-thinking to analyze the issue, otherwise just analyze the issue
- create a plan to fix the issue
- execute the plan to fix the issue. Iterate over your development work until all tests pass. It is crucial that you NEVER modify test code. If you think there is something wrong with the test code, stop, explain your situation, and ask what you should do. Do not commit these changes!
- when you have fixed the problem and all tests pass, pop the champagne cork

