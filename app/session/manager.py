import time
from typing import List, Optional
from app.session.models import Session, ConversationTurn, Role, SessionState
from app.utils.logging import logger

class SessionManager:
    def __init__(self, max_turns: int = 50):
        self.max_turns = max_turns
        self.current_session: Optional[Session] = None
        self.reset_session()

    def reset_session(self):
        """Clears context and starts a new session."""
        logger.info("[session] Session reset")
        self.current_session = Session()

    def start_session(self):
        """Transitions session to ACTIVE if idle."""
        if self.current_session.state == SessionState.IDLE:
            self.current_session.state = SessionState.ACTIVE
            self.current_session.updated_at = time.time()
            logger.info("[session] Session started")

    def _add_turn(self, role: Role, text: str, metadata: dict = None) -> ConversationTurn:
        self.start_session()
        
        turn = ConversationTurn(role=role, text=text, metadata=metadata or {})
        self.current_session.turns.append(turn)
        self.current_session.updated_at = time.time()
        
        # Enforce context limits
        if len(self.current_session.turns) > self.max_turns:
            # We remove the oldest turn, but we should be careful to keep system prompt if we had one.
            # Right now, simple FIFO trimming.
            self.current_session.turns.pop(0)
            
        return turn

    def add_user_turn(self, text: str, metadata: dict = None) -> ConversationTurn:
        """Add a user's transcribed speech to the conversation context."""
        logger.info("[session] User turn added")
        
        if self.current_session and self.current_session.turns:
            last_turn = self.current_session.turns[-1]
            if last_turn.role == Role.USER:
                import re
                match_last = re.match(r'^(\[[^\]]+\]:\s*)(.*)', last_turn.text, flags=re.DOTALL)
                match_new = re.match(r'^(\[[^\]]+\]:\s*)(.*)', text, flags=re.DOTALL)
                
                if match_last and match_new and match_last.group(1) == match_new.group(1):
                    # Same speaker, merge them
                    base_text = last_turn.text.strip()
                    if not base_text.endswith(('.', '?', '!')):
                        base_text += '.'
                    last_turn.text = f"{base_text} {match_new.group(2).strip()}"
                    self.current_session.updated_at = time.time()
                    logger.info("[session] Merged consecutive user turns (Same Speaker)")
                    return last_turn
                elif not match_last and not match_new:
                    # Raw text fallback (no prefix)
                    base_text = last_turn.text.strip()
                    if not base_text.endswith(('.', '?', '!')):
                        base_text += '.'
                    last_turn.text = f"{base_text} {text.strip()}"
                    self.current_session.updated_at = time.time()
                    logger.info("[session] Merged consecutive user turns (Raw)")
                    return last_turn

        return self._add_turn(Role.USER, text, metadata)

    def add_assistant_turn(self, text: str, metadata: dict = None) -> ConversationTurn:
        """Add an assistant's response to the conversation context."""
        logger.info("[session] Assistant turn added")
        return self._add_turn(Role.ASSISTANT, text, metadata)

    def add_system_turn(self, text: str, metadata: dict = None) -> ConversationTurn:
        """Add a system turn."""
        return self._add_turn(Role.SYSTEM, text, metadata)

    def get_context(self) -> List[ConversationTurn]:
        """Retrieve the current conversation history."""
        return list(self.current_session.turns)

    def end_session(self):
        """Ends the current session."""
        self.current_session.state = SessionState.ENDED
        self.current_session.updated_at = time.time()
        logger.info("[session] Session ended")
