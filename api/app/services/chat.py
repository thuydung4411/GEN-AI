import uuid
from typing import AsyncGenerator

from api.app.repositories.interfaces import AuthenticatedUser, DatasetRepository
from api.app.repositories.chat import ChatRepository
from api.app.services.rag import RAGService
from api.app.models.entities import MessageRole, MessageStatus

class ChatService:
    def __init__(
        self,
        repository: DatasetRepository,
        chat_repository: ChatRepository,
        rag_service: RAGService,
    ):
        self._repository = repository
        self._chat_repository = chat_repository
        self._rag_service = rag_service

    async def create_session(self, current_user: AuthenticatedUser, title: str):
        workspace = await self._repository.ensure_workspace_for_user(current_user.user_id, current_user.email)
        return await self._chat_repository.create_session(workspace.id, title)

    async def list_sessions(self, current_user: AuthenticatedUser, limit: int = 50):
        workspace = await self._repository.ensure_workspace_for_user(current_user.user_id, current_user.email)
        return await self._chat_repository.list_sessions(workspace.id, limit)

    async def get_session(self, current_user: AuthenticatedUser, session_id: uuid.UUID):
        workspace = await self._repository.ensure_workspace_for_user(current_user.user_id, current_user.email)
        return await self._chat_repository.get_session(workspace.id, session_id)

    async def stream_message(
        self,
        current_user: AuthenticatedUser,
        session_id: uuid.UUID,
        content: str,
        model_choice: str
    ) -> AsyncGenerator[tuple[str, dict | None, uuid.UUID], None]:
        """
        Yields (token, final_metadata, assistant_message_id)
        """
        workspace = await self._repository.ensure_workspace_for_user(current_user.user_id, current_user.email)
        
        # 1. Verification
        chat_session = await self._chat_repository.get_session(workspace.id, session_id)
        if not chat_session:
            raise ValueError("Session not found in this workspace")

        # 2. Retrieve
        contexts = await self._rag_service.retrieve_context(workspace.id, query=content)

        # 3. Draft
        await self._chat_repository.create_message(
            session_id=session_id,
            role=MessageRole.user,
            content=content,
            status=MessageStatus.completed,
            commit=False
        )
        
        assistant_msg = await self._chat_repository.create_message(
            session_id=session_id,
            role=MessageRole.assistant,
            content="",
            status=MessageStatus.streaming,
            model_name=model_choice,
            retrieval_used=len(contexts) > 0,
            commit=True
        )

        history = [{"role": m.role, "content": m.content} for m in chat_session.messages if m.status == "completed"]

        full_content = ""
        final_meta = None
        
        try:
            async for token, meta in self._rag_service.stream_generation(
                model_name=model_choice,
                query=content,
                contexts=contexts,
                history=history
            ):
                if token:
                    full_content += token
                    yield token, None, assistant_msg.id
                
                if meta:
                    final_meta = meta
                    yield "", meta, assistant_msg.id
                    
            # Finalize
            await self._chat_repository.update_message(
                message_id=assistant_msg.id,
                content=full_content,
                status=MessageStatus.completed,
                metadata_json=final_meta
            )
            
        except Exception as e:
            await self._chat_repository.update_message(
                message_id=assistant_msg.id,
                content=full_content,
                status=MessageStatus.failed,
            )
            raise e
