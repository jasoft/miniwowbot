"""保存 Clef 返回的受约束动作决策。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ClefDecision:
    """保存经校验的模型选择和请求统计。

    Attributes:
        action: 白名单中的动作名称。
        confidence: 服务端返回的决策置信度。
        probabilities: 各动作的概率。
        latency_seconds: 单次 API 请求耗时。
        input_tokens: 服务端统计的输入令牌数量。
    """

    action: str
    confidence: float
    probabilities: dict[str, float]
    latency_seconds: float
    input_tokens: int
