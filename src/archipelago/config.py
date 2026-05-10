from agent_foundry.primitives import ClaudeEffort, ClaudeModel

DESIGNER_MODEL: ClaudeModel = ClaudeModel.OPUS_4_6
DESIGNER_EFFORT: ClaudeEffort = ClaudeEffort.HIGH
CHANGE_SET_PLANNER_MODEL: ClaudeModel = ClaudeModel.SONNET_4_6
CHANGE_SET_PLANNER_EFFORT: ClaudeEffort = ClaudeEffort.HIGH
TDD_PLANNER_MODEL: ClaudeModel = ClaudeModel.SONNET_4_6
TESTER_MODEL: ClaudeModel = ClaudeModel.HAIKU_4_5
IMPLEMENTER_MODEL: ClaudeModel = ClaudeModel.SONNET_4_6
PR_CREATOR_MODEL: ClaudeModel = ClaudeModel.HAIKU_4_5
