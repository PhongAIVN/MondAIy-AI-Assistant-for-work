"""Context có provenance cho câu hỏi trong một project."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.conversation import Conversation
from src.models.meeting_note import MeetingNote
from src.models.project import Project


@dataclass(frozen=True)
class ProjectContext:
    project_id: int
    conversations: tuple[Conversation, ...]
    meetings: tuple[MeetingNote, ...]

    @property
    def records(self) -> list[dict]:
        return [
            {"kind": "conversation", "id": row.id, "title": row.title, "provenance": f"conversation:{row.id}"}
            for row in self.conversations
        ] + [
            {"kind": "meeting_note", "id": row.id, "title": row.title, "provenance": f"meeting_note:{row.id}"}
            for row in self.meetings
        ]


def build_project_context(db: Session, project: Project, user_id: str) -> ProjectContext:
    """Lấy đúng dữ liệu của user; không dùng summary cache làm nguồn sự thật."""
    conversations = tuple(db.execute(
        select(Conversation).where(Conversation.project_id == project.id, Conversation.user_id == str(user_id)).order_by(Conversation.updated_at.desc())
    ).scalars().all())
    meetings = tuple(db.execute(
        select(MeetingNote).where(MeetingNote.project_id == project.id, MeetingNote.user_id == str(user_id)).order_by(MeetingNote.updated_at.desc())
    ).scalars().all())
    return ProjectContext(project.id, conversations, meetings)
