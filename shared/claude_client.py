"""Claude API クライアント（共通）"""
import json
import time

import anthropic

from shared.logger import get_logger

logger = get_logger("claude")
DEFAULT_MODEL = "claude-sonnet-4-6"


class ClaudeClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int = 8096, retries: int = 2) -> str:
        for attempt in range(retries + 1):
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                return resp.content[0].text
            except anthropic.RateLimitError:
                if attempt < retries:
                    wait = 30 * (attempt + 1)
                    logger.warning(f"レートリミット。{wait}秒待機...")
                    time.sleep(wait)
                else:
                    raise

    def complete_json(self, system: str, user: str, max_tokens: int = 8096) -> dict | list:
        system_j = system + "\n\n必ずJSON形式のみで回答してください。前置き・説明・コードブロック記号は不要です。"
        text = self.complete(system_j, user, max_tokens=max_tokens).strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSONパース失敗: {e}")
            # 配列が途中で切れた場合は最後の完全な要素までを回収
            if text.startswith("["):
                last_close = text.rfind("},")
                if last_close == -1:
                    last_close = text.rfind("}")
                if last_close != -1:
                    recovered = text[: last_close + 1] + "]"
                    try:
                        parsed = json.loads(recovered)
                        logger.info(f"JSONを部分回復: {len(parsed)}件")
                        return parsed
                    except json.JSONDecodeError:
                        pass
            return {}
