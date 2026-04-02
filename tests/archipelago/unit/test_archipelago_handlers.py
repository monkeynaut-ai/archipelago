"""Archipelago handlers — unit tests."""

from archipelago.handlers import ARCHIPELAGO_HANDLERS


class TestHandlerRegistry:
    def test_given_archipelago_handlers_when_all_keys_checked_then_all_roles_present(self):
        expected = {
            "decompose_job_specification",
            "dispatch_commit",
            "evaluate_commit",
            "write_unit_tests_from_spec",
            "code_implement_from_tests",
            "software_review",
        }
        assert set(ARCHIPELAGO_HANDLERS.keys()) == expected

    def test_given_each_handler_in_registry_when_checked_then_is_callable(self):
        for name, handler in ARCHIPELAGO_HANDLERS.items():
            assert callable(handler), f"Handler for {name} is not callable"
