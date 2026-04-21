import unittest

from backend.apps.ocr.service import _cluster_score, _drop_ui_noise, _is_low_signal_ocr_line


class OCRServiceHeuristicsTestCase(unittest.TestCase):
    def test_low_signal_clock_lines_are_detected(self):
        self.assertTrue(_is_low_signal_ocr_line("и 121"))
        self.assertTrue(_is_low_signal_ocr_line("10"))
        self.assertTrue(_is_low_signal_ocr_line("7[в 5"))
        self.assertFalse(_is_low_signal_ocr_line("Seattle"))
        self.assertFalse(_is_low_signal_ocr_line("-10HRS"))
        self.assertFalse(_is_low_signal_ocr_line("Moscow Today"))

    def test_drop_ui_noise_prefers_meaningful_text_over_clock_noise(self):
        raw = "\n".join([
            "м 121 м 121 т 21 т 21",
            "10 РА ДУ 2738 2 10 2",
            "7[в 5 7[в 5 7[в 5 7[в 5",
            "Seattle Chicago Novosibirsk Moscow",
            "Yesterday Yesterday Today Today",
            "-10HRS -8HRS +4HRS +0HRS",
        ])

        cleaned = _drop_ui_noise(raw)

        self.assertEqual(
            cleaned,
            "\n".join([
                "Seattle Chicago Novosibirsk Moscow",
                "Yesterday Yesterday Today Today",
                "-10HRS -8HRS +4HRS +0HRS",
            ]),
        )

    def test_cluster_score_prefers_text_cluster_over_clock_cluster(self):
        text_cluster = [
            {
                "left": 60,
                "top": 210,
                "right": 620,
                "bottom": 228,
                "char_count": 31,
                "alpha_count": 31,
                "digit_count": 0,
                "long_alpha_tokens": 4,
            },
            {
                "left": 50,
                "top": 237,
                "right": 610,
                "bottom": 257,
                "char_count": 28,
                "alpha_count": 28,
                "digit_count": 0,
                "long_alpha_tokens": 4,
            },
            {
                "left": 60,
                "top": 262,
                "right": 613,
                "bottom": 278,
                "char_count": 19,
                "alpha_count": 12,
                "digit_count": 4,
                "long_alpha_tokens": 4,
            },
        ]
        clock_cluster = [
            {
                "left": 70,
                "top": 63,
                "right": 136,
                "bottom": 85,
                "char_count": 4,
                "alpha_count": 1,
                "digit_count": 3,
                "long_alpha_tokens": 0,
            },
            {
                "left": 47,
                "top": 93,
                "right": 66,
                "bottom": 106,
                "char_count": 2,
                "alpha_count": 0,
                "digit_count": 2,
                "long_alpha_tokens": 0,
            },
            {
                "left": 108,
                "top": 117,
                "right": 172,
                "bottom": 143,
                "char_count": 2,
                "alpha_count": 1,
                "digit_count": 1,
                "long_alpha_tokens": 0,
            },
        ]

        text_score = _cluster_score(text_cluster, page_width=726, page_height=315)
        clock_score = _cluster_score(clock_cluster, page_width=726, page_height=315)

        self.assertGreater(text_score, clock_score)


if __name__ == "__main__":
    unittest.main()
