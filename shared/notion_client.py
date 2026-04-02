"""Notion API クライアント"""
from pathlib import Path

from notion_client import Client

from shared.logger import get_logger

logger = get_logger("notion")


class NotionWriter:
    def __init__(self, token: str, parent_page_id: str):
        self.client = Client(auth=token)
        self.parent_page_id = parent_page_id

    def create_project_page(self, title: str) -> "NotionWriter":
        """プロジェクト用の親ページを作成し、その配下に書き込む新しいNotionWriterを返す。"""
        page = self.client.pages.create(
            parent={"page_id": self.parent_page_id},
            properties={"title": {"title": [{"text": {"content": title}}]}},
            children=[],
        )
        project_id = page["id"]
        logger.info(f"プロジェクトページ作成: 「{title}」 (id: {project_id})")
        child = NotionWriter(token="", parent_page_id=project_id)
        child.client = self.client  # クライアントを共有
        return child

    def create_page(self, title: str, content_md: str, parent_id: str | None = None) -> str:
        """Markdownコンテンツを新規Notionページとして作成。page_idを返す。"""
        blocks = self._md_to_blocks(content_md)
        pid = parent_id or self.parent_page_id

        page = self.client.pages.create(
            parent={"page_id": pid},
            properties={
                "title": {"title": [{"text": {"content": title}}]}
            },
            children=blocks[:100],  # Notion APIは一度に100ブロックまで
        )
        page_id = page["id"]

        # 100ブロック超の場合は追記
        for i in range(100, len(blocks), 100):
            self.client.blocks.children.append(
                block_id=page_id,
                children=blocks[i:i+100],
            )

        logger.info(f"Notionページ作成: 「{title}」 (id: {page_id})")
        return page_id

    def archive_page(self, page_id: str) -> None:
        """ページをアーカイブ（削除）する"""
        self.client.pages.update(page_id=page_id, archived=True)
        logger.info(f"ページ削除: {page_id}")

    def list_child_pages(self) -> list[dict]:
        """親ページ直下の子ページ一覧を返す（id, titleのdict）"""
        results = []
        cursor = None
        while True:
            resp = self.client.blocks.children.list(
                block_id=self.parent_page_id,
                start_cursor=cursor,
            )
            for block in resp.get("results", []):
                if block.get("type") == "child_page":
                    results.append({
                        "id": block["id"],
                        "title": block["child_page"].get("title", ""),
                    })
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return results

    def update_page(self, page_id: str, content_md: str) -> None:
        """既存ページの子ブロックを全削除して再作成"""
        # 既存ブロックを削除
        existing = self.client.blocks.children.list(block_id=page_id)
        for block in existing.get("results", []):
            self.client.blocks.delete(block_id=block["id"])

        blocks = self._md_to_blocks(content_md)
        for i in range(0, len(blocks), 100):
            self.client.blocks.children.append(
                block_id=page_id,
                children=blocks[i:i+100],
            )
        logger.info(f"Notionページ更新: {page_id}")

    def _md_to_blocks(self, md: str) -> list[dict]:
        """MarkdownをNotionブロックリストに変換"""
        blocks = []
        lines = md.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            if line.startswith("# "):
                blocks.append(self._heading(line[2:], 1))
            elif line.startswith("## "):
                blocks.append(self._heading(line[3:], 2))
            elif line.startswith("### "):
                blocks.append(self._heading(line[4:], 3))
            elif line.startswith("- ") or line.startswith("・"):
                text = line[2:] if line.startswith("- ") else line[1:]
                blocks.append(self._bullet(text))
            elif line.startswith("1. ") or (len(line) > 2 and line[0].isdigit() and line[1] == "."):
                text = line.split(". ", 1)[-1]
                blocks.append(self._numbered(text))
            elif line.startswith("---") or line.startswith("━━━"):
                blocks.append(self._divider())
            elif line.strip() == "":
                pass  # 空行はスキップ
            else:
                blocks.append(self._paragraph(line))

            i += 1

        return blocks

    def _heading(self, text: str, level: int) -> dict:
        key = f"heading_{level}"
        return {
            "object": "block",
            "type": key,
            key: {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
        }

    def _paragraph(self, text: str) -> dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
        }

    def _bullet(self, text: str) -> dict:
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
        }

    def _numbered(self, text: str) -> dict:
        return {
            "object": "block",
            "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
        }

    def _divider(self) -> dict:
        return {"object": "block", "type": "divider", "divider": {}}
