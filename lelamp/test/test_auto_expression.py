import unittest


class AutoExpressionTests(unittest.TestCase):
    def test_infer_expression_style_prefers_worried_for_complaint_transcript(self) -> None:
        from lelamp.auto_expression import infer_expression_style

        style = infer_expression_style("抢不过啊，太烦了，他一直黏着我。")

        self.assertEqual(style, "worried")

    def test_pick_fallback_expression_waits_then_dispatches_or_skips(self) -> None:
        from lelamp.auto_expression import pick_fallback_expression

        snapshot = {
            "last_asr_status": "ok",
            "last_asr_text": "我回来了，快看我这波。",
            "last_commit_at_ms": 1000,
        }

        self.assertIsNone(
            pick_fallback_expression(
                snapshot=snapshot,
                now_ms=1200,
                handled_commit_at_ms=0,
                last_tool_dispatch_at_ms=0,
                delay_ms=350,
            )
        )
        self.assertEqual(
            pick_fallback_expression(
                snapshot=snapshot,
                now_ms=1400,
                handled_commit_at_ms=0,
                last_tool_dispatch_at_ms=0,
                delay_ms=350,
            ),
            (1000, "greeting"),
        )
        self.assertEqual(
            pick_fallback_expression(
                snapshot=snapshot,
                now_ms=1400,
                handled_commit_at_ms=0,
                last_tool_dispatch_at_ms=1200,
                delay_ms=350,
            ),
            (1000, None),
        )


if __name__ == "__main__":
    unittest.main()
