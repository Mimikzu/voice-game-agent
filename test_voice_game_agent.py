import unittest

from voice_game_agent import InputBinding, parse_command


class ParseCommandTests(unittest.TestCase):
    def test_direct_and_repeated_jump_are_single_safe_taps(self):
        for phrase in ("jump", "Jump, jump, jump, jump.", "tap jump"):
            with self.subTest(phrase=phrase):
                action = parse_command(phrase)
                self.assertIsNotNone(action)
                self.assertEqual(action.target, "jump")
                self.assertEqual(action.repetitions, 1)

    def test_double_jump_is_two_taps(self):
        action = parse_command("double jump")
        self.assertIsNotNone(action)
        self.assertEqual(action.target, "jump")
        self.assertEqual(action.repetitions, 2)

    def test_rocket_league_profile_maps_boost_to_mouse(self):
        action = parse_command("boost", "rocket-league")
        self.assertIsNotNone(action)
        self.assertEqual(action.binding, InputBinding("mouse", "left"))
        self.assertGreater(action.seconds, 0.18)

    def test_rocket_league_default_jump_and_powerslide_bindings(self):
        jump = parse_command("jump", "rocket-league")
        powerslide = parse_command("drift", "rocket-league")
        self.assertIsNotNone(jump)
        self.assertIsNotNone(powerslide)
        self.assertEqual(jump.binding, InputBinding("mouse", "right"))
        self.assertEqual(powerslide.binding, InputBinding("keyboard", "shift"))

    def test_minecraft_right_click_uses_item(self):
        action = parse_command("press right click", "minecraft")
        self.assertIsNotNone(action)
        self.assertEqual(action.target, "use")
        self.assertEqual(action.binding, InputBinding("mouse", "right"))

    def test_rocket_league_right_click_jumps(self):
        action = parse_command("press right click", "rocket-league")
        self.assertIsNotNone(action)
        self.assertEqual(action.target, "jump")

    def test_minecraft_hotbar_slot(self):
        action = parse_command("switch to slot 3", "minecraft")
        self.assertIsNotNone(action)
        self.assertEqual(action.binding, InputBinding("keyboard", "3"))

    def test_other_profiles_reject_minecraft_hotbar_command(self):
        self.assertIsNone(parse_command("slot 3", "rocket-league"))

    def test_hold_duration_is_capped(self):
        action = parse_command("boost for 10 seconds", "rocket-league")
        self.assertIsNotNone(action)
        self.assertEqual(action.seconds, 2.0)

    def test_transcribed_number_word_is_supported(self):
        action = parse_command("hold accelerate for five seconds", "rocket-league")
        self.assertIsNotNone(action)
        self.assertEqual(action.target, "forward")
        self.assertEqual(action.seconds, 2.0)

    def test_decimal_duration_is_supported(self):
        action = parse_command("boost for 1.5 seconds", "rocket-league")
        self.assertIsNotNone(action)
        self.assertEqual(action.seconds, 1.5)

    def test_minute_duration_is_parsed_and_capped(self):
        action = parse_command("accelerate one minute", "rocket-league")
        self.assertIsNotNone(action)
        self.assertEqual(action.target, "forward")
        self.assertEqual(action.seconds, 2.0)

    def test_reordered_hold_command_is_rejected_if_ambiguous(self):
        self.assertIsNone(parse_command("use hold accelerated for five seconds", "minecraft"))

    def test_unrecognized_speech_sends_no_action(self):
        self.assertIsNone(parse_command("press whole w", "rocket-league"))


if __name__ == "__main__":
    unittest.main()
