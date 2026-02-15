import unittest

from quotex_bot.config import RiskConfig, StrategyConfig
from quotex_bot.models import Prediction, Signal
from quotex_bot.risk import RiskEngine


class DecisionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RiskEngine(StrategyConfig(), RiskConfig())

    def test_up_signal_when_probability_and_margin_are_high(self) -> None:
        decision = self.engine.decide(Prediction(p_up=0.72, p_down=0.28, uncertainty=0.2))
        self.assertEqual(decision.signal, Signal.UP)

    def test_no_trade_on_high_uncertainty(self) -> None:
        decision = self.engine.decide(Prediction(p_up=0.8, p_down=0.2, uncertainty=0.8))
        self.assertEqual(decision.signal, Signal.NO_TRADE)

    def test_cooldown_after_losses(self) -> None:
        self.engine.register_trade_result(-10)
        self.engine.register_trade_result(-10)
        self.engine.register_trade_result(-10)
        decision = self.engine.decide(Prediction(p_up=0.8, p_down=0.2, uncertainty=0.1))
        self.assertEqual(decision.signal, Signal.NO_TRADE)


if __name__ == "__main__":
    unittest.main()
