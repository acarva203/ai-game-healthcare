from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hospital_game.cli import DEFAULT_CONTENT, handle_line, main
from hospital_game.content import load_content
from hospital_game.domain import Action
from hospital_game.presentation import Session


class CliTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(load_content(DEFAULT_CONTENT))

    def test_reading_does_not_advance_state(self):
        before = self.session.get_view()
        for command in ("chart 1", "chart case_02", "help", "queue", "history", "policies", "scene"):
            text, stop = handle_line(self.session, command)
            self.assertTrue(text)
            self.assertFalse(stop)
        self.assertEqual(self.session.get_view(), before)

    def test_adapter_result_does_not_expose_domain_state(self):
        handle_line(self.session, "acknowledge")
        view = self.session.get_view()
        result = self.session.choose(view.cases[0].actions[0], view.revision)
        self.assertTrue(result.ok)
        self.assertFalse(hasattr(result, "state"))
        self.assertFalse(hasattr(result, "events"))

    def test_invalid_input_does_not_dispatch(self):
        before = self.session.get_view()
        for command in ("approve 99", "reject 1", 'chart "', "wait 10", "approve", "alternative 1 missing"):
            text, _ = handle_line(self.session, command)
            self.assertTrue(text.startswith("Error:"), text)
        self.assertEqual(self.session.get_view(), before)

    def test_evidence_led_demo(self):
        output = StringIO()
        with redirect_stdout(output):
            main(["--demo", "evidence-led"])
        text = output.getvalue()
        self.assertIn("tick 4 | funds 145 | assessment slots 1", text)
        self.assertIn("Timothy Martin (case_02) — health 85/100, resolved", text)
        self.assertIn("Care and policy debrief:", text)
        self.assertNotIn("Error:", text)
        self.assertNotIn("category_b", text)

    def test_interactive_smoke_and_end_of_input(self):
        output = StringIO()
        with patch("builtins.input", side_effect=["chart 2", "acknowledge", "approve 1", "end", EOFError]), redirect_stdout(output):
            main([])
        self.assertIn("timed_out", output.getvalue())
        self.assertIn("Exited without saving", output.getvalue())

    def test_briefing_memos_choices_and_disabled_actions(self):
        before = self.session.get_view()
        text, _ = handle_line(self.session, "queue")
        self.assertIn("From Elias Chen", text)
        self.assertIn("choose acknowledge", text)
        self.assertIn("version northbank-lore-1", text)
        text, _ = handle_line(self.session, "approve 1")
        self.assertIn("Unavailable:", text)
        self.assertEqual(before, self.session.get_view())
        handle_line(self.session, "choose acknowledge")
        self.assertTrue(self.session.get_view().cases[0].actions[0].enabled)

    def test_remaining_demos_show_audit_and_selected_ending(self):
        for demo, ending, funds in (("ai-first", "human_cost", 150),
                                    ("direct-care", "oversight_hearing", 120)):
            with self.subTest(demo=demo):
                output = StringIO()
                with redirect_stdout(output):
                    main(["--demo", demo])
                text = output.getvalue()
                self.assertIn(f"Selected ending: {ending}", text)
                self.assertIn(f"tick 2 | funds {funds}", text)
                self.assertNotIn("Unavailable:", text.split("> acknowledge", 1)[1])
                self.assertNotIn("Error:", text)
                if demo == "direct-care":
                    self.assertIn("tick 2 | funds 165", text)
                    self.assertIn("assessed 45 credits; collected 45; unpaid 0", text)
                    self.assertIn("commitment event", text)

    def test_story_adapter_rejects_stale_view(self):
        view = self.session.get_view()
        choice = next(a for a in view.actions if a.action == Action.STORY_CHOICE)
        self.assertTrue(self.session.choose(choice, view.revision).ok)
        current = self.session.get_view()
        result = self.session.choose(choice, view.revision)
        self.assertEqual(result.error.code, "stale_revision")
        self.assertEqual(self.session.get_view(), current)

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version": 1, "schema_version": 2}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                load_content(path)

    def test_invalid_content_load_fails_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            data = json.loads(DEFAULT_CONTENT.read_text())
            data["cases"][0]["care_options"][0]["cost"] = -1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "below minimum"):
                load_content(path)

    def test_terminal_save_load_quoted_path_and_continue(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "my progress.json"
            handle_line(self.session, "acknowledge")
            handle_line(self.session, "test 2 verify_marker")
            saved = self.session.get_view()
            text, stop = handle_line(self.session, f'save "{path}"')
            self.assertTrue(text.startswith("Saved to"), text)
            self.assertFalse(stop)
            self.assertEqual(self.session.get_view(), saved)
            handle_line(self.session, "alternative 2 care_b")
            text, stop = handle_line(self.session, f'load "{path}"')
            self.assertTrue(text.startswith("Loaded from"), text)
            self.assertFalse(stop)
            self.assertEqual(self.session.get_view(), saved)
            for command in ("alternative 2 care_b", "approve 1", "end"):
                text, _ = handle_line(self.session, command)
                self.assertNotIn("Error:", text)
            self.assertEqual(self.session.get_view().funds, 145)
            self.assertEqual(self.session.get_view().scene.id, "measured_integration")

    def test_terminal_load_ending_shows_audit_without_new_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ending.json"
            for command in ("acknowledge", "approve 1", "alternative 2 care_b", "end"):
                handle_line(self.session, command)
            before = self.session.get_view()
            handle_line(self.session, f'save "{path}"')
            for _ in range(2):
                text, stop = handle_line(self.session, f'load "{path}"')
                self.assertIn("Selected ending: oversight_hearing", text)
                self.assertIn("assessed 45 credits; collected 45; unpaid 0", text)
                self.assertFalse(stop)
                self.assertEqual(self.session.get_view(), before)
            text, _ = handle_line(self.session, "end")
            self.assertTrue(text.startswith("Unavailable:"))
            self.assertEqual(self.session.get_view(), before)

    def test_terminal_file_and_parse_errors_leave_session_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            corrupt = Path(directory) / "corrupt.json"
            corrupt.write_text("{")
            before = self.session.get_view()
            for command in ("save", "load", "save a b", 'load "',
                            f'load "{missing}"', f'load "{corrupt}"',
                            f'save "{missing / "nested.json"}"', f'save "{directory}"'):
                text, stop = handle_line(self.session, command)
                self.assertTrue(text.startswith("Error:"), text)
                self.assertFalse(stop)
                self.assertEqual(self.session.get_view(), before)
            text, _ = handle_line(self.session, "acknowledge")
            self.assertNotIn("Error:", text)

    def test_terminal_write_failure_keeps_state_and_previous_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "progress.json"
            handle_line(self.session, f'save "{path}"')
            original = path.read_bytes()
            handle_line(self.session, "acknowledge")
            current = self.session.get_view()
            with patch("hospital_game.persistence.os.replace", side_effect=OSError("disk error")):
                text, stop = handle_line(self.session, f'save "{path}"')
            self.assertTrue(text.startswith("Error: Cannot write save:"), text)
            self.assertFalse(stop)
            self.assertEqual(self.session.get_view(), current)
            self.assertEqual(path.read_bytes(), original)

    def test_interactive_save_load_and_eof(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "progress.json"
            output = StringIO()
            commands = ["acknowledge", f'save "{path}"', "approve 1",
                        f'load "{path}"', EOFError]
            with patch("builtins.input", side_effect=commands), redirect_stdout(output):
                main([])
            self.assertIn("Saved to", output.getvalue())
            self.assertIn("Loaded from", output.getvalue())
            self.assertNotIn("Error:", output.getvalue())
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
