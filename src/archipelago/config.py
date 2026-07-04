from agent_foundry.ai_models import Model
from agent_foundry.constructs import ClaudeEffort, ClaudeModel

DESIGNER_MODEL: ClaudeModel = ClaudeModel.HAIKU_4_5
DESIGNER_EFFORT: ClaudeEffort = ClaudeEffort.HIGH
CHANGE_SET_PLANNER_MODEL: ClaudeModel = ClaudeModel.HAIKU_4_5
CHANGE_SET_PLANNER_EFFORT: ClaudeEffort = ClaudeEffort.HIGH
TDD_PLANNER_MODEL: ClaudeModel = ClaudeModel.HAIKU_4_5
TESTER_MODEL: ClaudeModel = ClaudeModel.HAIKU_4_5
IMPLEMENTER_MODEL: ClaudeModel = ClaudeModel.HAIKU_4_5
PR_CREATOR_MODEL: ClaudeModel = ClaudeModel.HAIKU_4_5
DESIGN_REVIEW_MODEL = Model.CLAUDE_SONNET_4_6
