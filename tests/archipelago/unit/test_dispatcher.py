"""Dispatcher handler — unit tests."""

from archipelago.agents.dispatcher import dispatcher_handler


def _make_state(slices: list[dict], index: int = 0) -> dict:
    return {
        "objective": "Add auth",
        "repo_url": "https://github.com/org/repo",
        "repo_ref": "main",
        "constraints": ["No new deps"],
        "commit_slices": slices,
        "current_index": index,
    }


class TestDispatcherHandler:
    def test_given_3_slices_at_index_0_when_called_then_current_commit_is_first_slice(self):
        slices = [{"title": "c1"}, {"title": "c2"}, {"title": "c3"}]
        result = dispatcher_handler(_make_state(slices, 0))
        assert result["current_commit"]["title"] == "c1"
        assert result["current_commit"]["objective"] == "Add auth"
        assert result["current_commit"]["repo_url"] == "https://github.com/org/repo"
        assert result["has_more_commits"] is True
        assert result["current_index"] == 1

    def test_given_3_slices_at_index_2_when_called_then_current_commit_is_third_slice(self):
        slices = [{"title": "c1"}, {"title": "c2"}, {"title": "c3"}]
        result = dispatcher_handler(_make_state(slices, 2))
        assert result["current_commit"]["title"] == "c3"
        assert result["has_more_commits"] is True
        assert result["current_index"] == 3

    def test_given_3_slices_at_index_3_when_called_then_has_more_commits_is_false(self):
        slices = [{"title": "c1"}, {"title": "c2"}, {"title": "c3"}]
        result = dispatcher_handler(_make_state(slices, 3))
        assert result["has_more_commits"] is False

    def test_given_0_slices_when_called_then_has_more_commits_is_false(self):
        result = dispatcher_handler(_make_state([], 0))
        assert result["has_more_commits"] is False

    def test_given_slice_with_test_focus_when_called_then_job_fields_merged(self):
        slices = [{"title": "c1", "test_focus": "unit tests"}]
        result = dispatcher_handler(_make_state(slices, 0))
        assert result["current_commit"]["constraints"] == ["No new deps"]
        assert result["current_commit"]["test_focus"] == "unit tests"
