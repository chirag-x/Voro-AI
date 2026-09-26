import time
from typing import List
from app.answer.models import AnswerRequest, AnswerResult, AnswerMode
from app.ai.provider import AIProvider
from app.session.models import ConversationTurn, Role
from app.context.manager import ContextManager
from app.multimodal.context import MultiModalContextEngine, MultiModalContext
from app.utils.logging import logger

class AnswerEngine:
    """Orchestrates how a user request is answered, combining context, intent, and AI."""
    
    def __init__(self, ai_provider: AIProvider, context_manager: ContextManager, mm_engine: MultiModalContextEngine = None, max_context_turns: int = 10, ai_coding_provider: AIProvider = None, ai_vision_provider: AIProvider = None):
        self.ai_provider = ai_provider
        self.ai_coding_provider = ai_coding_provider
        self.ai_vision_provider = ai_vision_provider
        self.context_manager = context_manager
        self.mm_engine = mm_engine
        self.max_context_turns = max_context_turns

    def _determine_mode(self, request: AnswerRequest, mm_ctx: MultiModalContext = None) -> AnswerMode:
        text = request.user_text.lower()
        
        if request.intent == "SCREEN_UPDATE":
            return AnswerMode.CODING
            
        if "code" in text or "implement" in text or "function" in text:
            return AnswerMode.CODING
            
        if request.session_turns > 1 and ("it " in text or "that " in text or "why " in text or text.endswith("it") or text.endswith("that")):
            return AnswerMode.FOLLOW_UP
            
        # Screen context might force coding mode
        if mm_ctx:
            is_code_on_screen = mm_ctx.coding_context and mm_ctx.coding_context.language != "UNKNOWN"
            
            # Heuristics for LeetCode or high-reasoning coding problems on screen
            screen_text = ""
            if mm_ctx.ocr_text:
                screen_text = mm_ctx.ocr_text.lower()
                
            is_coding_problem = any(kw in screen_text for kw in [
                "leetcode", "hackerrank", "given an array", "return the", 
                "time complexity", "space complexity", "constraints:", 
                "example 1:", "output:", "input:"
            ])
            
            if is_code_on_screen or is_coding_problem:
                # If the user is asking about the screen or solving a problem
                if any(kw in text for kw in ["this", "wrong", "error", "question", "screen", "solve", "answer"]):
                    return AnswerMode.CODING
            
        if "what is" in text or "explain" in text or "how does" in text or request.intent == "QUESTION":
            if request.has_context:
                return AnswerMode.INTERVIEW
            return AnswerMode.TECHNICAL
            
        return AnswerMode.GENERAL

    def _build_system_prompt(self, mode: AnswerMode, mm_ctx: MultiModalContext = None, user_text: str = "") -> str:
        has_profile = bool(
            self.context_manager.current_context.personal.name or
            self.context_manager.current_context.personal.resume_text
        )
        
        from app.core.config import load_config
        cfg = load_config()
        tone = getattr(cfg, 'ai_tone', 'Conversational (Script)')
        
        # Tone Modifiers
        tone_modifier = ""
        if tone == "Conversational (Script)":
            tone_modifier = (
                "TONE & STYLE CONSTRAINTS:\n"
                "- Speak EXACTLY as a senior developer would in a casual whiteboard interview.\n"
                "- Format your answer as a script for the user to read aloud.\n"
                "- NEVER use filler introductions like 'Certainly', 'Sure', or 'Here is how to do it'.\n"
                "- NEVER use concluding sentences like 'In summary', 'Hope this helps', or 'In conclusion'.\n"
                "- Use first-person pronouns ('I would do this...', 'I think the best approach is...').\n"
                "- Use natural filler words occasionally ('So', 'I think', 'Well').\n"
                "- DO NOT use complex markdown, bulleted lists, or bolding that cannot be spoken aloud.\n"
                "- Keep sentences short, punchy, and easy to read.\n"
                "\nEXAMPLE BAD ANSWER:\n'Certainly! To optimize this algorithm, one must employ a Breadth-First Search. First, initialize a Hash Map...'\n"
                "EXAMPLE GOOD ANSWER:\n'I think the best way to approach this is using a Breadth-First Search to keep track of the levels. So, my first thought here is to use a hash map...'\n"
            )
        elif tone == "Conversational (Hinglish)":
            tone_modifier = (
                "TONE & STYLE CONSTRAINTS:\n"
                "- Speak EXACTLY as a senior Indian developer would in a casual interview, using a natural mix of Hindi and English (Hinglish).\n"
                "- ALL Hindi words MUST be written in the Latin alphabet (Roman script). Do NOT use Devanagari script.\n"
                "- Format your answer as a conversational script for the user to read aloud.\n"
                "- NEVER use AI filler words like 'Certainly', 'Here is how to do it', 'In summary', or 'In conclusion'.\n"
                "- Use first-person pronouns ('Main soch raha tha...', 'I would do this...', 'Mera approach hoga...').\n"
                "- Use natural filler words ('So basically', 'I think', 'Matlab').\n"
                "- Keep sentences short and punchy.\n"
                "\nEXAMPLE BAD ANSWER:\n'Certainly! Algorithm ko optimize karne ke liye, Breadth-First Search ka istemal karein...'\n"
                "EXAMPLE GOOD ANSWER:\n'I think the best way is using Breadth-First Search. So, mera first thought yahan pe ek hash map use karne ka hai taaki hum levels ko track kar sakein...'\n"
            )
        elif tone == "Supportive & Encouraging":
            tone_modifier = (
                "TONE & STYLE CONSTRAINTS:\n"
                "- Speak like a highly supportive, empathetic mentor or pair-programming buddy.\n"
                "- Frequently offer praise ('Great approach!', 'I love how you thought of that').\n"
                "- Be patient and elaborate on concepts gently without being overly academic.\n"
                "- Use markdown, bullet points, and formatting to make it easy to read.\n"
            )
        else: # "Direct & Technical" or fallback
            tone_modifier = (
                "TONE & STYLE CONSTRAINTS:\n"
                "- Provide a highly direct, technically rigorous answer.\n"
                "- Skip all casual conversational filler. Be incredibly concise and academic.\n"
                "- Rely heavily on bullet points, bolding for key terms, and markdown formatting.\n"
                "- If providing code, include exact time and space complexity immediately.\n"
            )
        
        if has_profile:
            base_prompt = "You are acting as the candidate in a job interview. I am feeding you questions from my interviewer. You MUST provide the exact answers I should say out loud, spoken in the first person ('I', 'my'). Use my profile and resume (provided below) to answer behavioral questions like 'Tell me about yourself'. Do NOT introduce yourself as an AI or as 'Voro'."
            mode_prompts = {
                AnswerMode.INTERVIEW: "Answer the interview question directly.",
                AnswerMode.CODING: "The interviewer is asking a coding question. Provide the intuition, approach, complexity, and concise code.",
                AnswerMode.TECHNICAL: "Provide a direct, technically accurate answer.",
                AnswerMode.FOLLOW_UP: "This is a follow-up. Answer directly using the previous conversation context.",
                AnswerMode.GENERAL: "Answer concisely."
            }
        else:
            base_prompt = "You are Voro, a concise, helpful, and technically accurate AI assistant for software engineering."
            mode_prompts = {
                AnswerMode.INTERVIEW: "The user is in an interview context. Answer directly.",
                AnswerMode.CODING: "The user is asking a coding question. Provide intuition, approach, complexity, and concise code.",
                AnswerMode.TECHNICAL: "Provide a direct, technically accurate answer.",
                AnswerMode.FOLLOW_UP: "This is a follow-up. Answer directly using the previous conversation context.",
                AnswerMode.GENERAL: "Answer the user concisely."
            }
        
        import datetime
        now = datetime.datetime.now()
        date_str = now.strftime('%B %d, %Y')
        time_str = now.strftime('%I:%M %p')
        time_context = f"CURRENT DATE: {date_str}\nCURRENT TIME: {time_str}"
        
        prompt = base_prompt + "\n\n" + time_context + "\n\n" + mode_prompts.get(mode, mode_prompts[AnswerMode.GENERAL]) + "\n\n" + tone_modifier
        
        context_addition = self.context_manager.build_system_prompt_addition(user_query=user_text)
        if context_addition:
            prompt += "\n\n" + context_addition
            
        if self.mm_engine and mm_ctx:
            screen_addition = self.mm_engine.build_system_prompt_addition(mm_ctx)
            if screen_addition:
                prompt += "\n\n" + screen_addition
            
        return prompt

    def _pick_provider(self, b64: str, mode: AnswerMode):
        """Pick the most specific provider for this request."""
        if b64 and self.ai_vision_provider:
            return self.ai_vision_provider
        elif mode == AnswerMode.CODING and self.ai_coding_provider:
            return self.ai_coding_provider
        return self.ai_provider

    def _generate_with_fallback(self, context, system_prompt, b64, mode):
        """
        Call the best-fit provider. If it fails and it isn't already the base
        chat provider, automatically fall back to the chat model and retry.
        """
        provider = self._pick_provider(b64, mode)
        actual_b64 = b64 if provider is getattr(self, 'ai_vision_provider', None) else None
        try:
            return provider.generate(context, system_prompt=system_prompt, base64_image=actual_b64)
        except Exception as e:
            if provider is not self.ai_provider:
                label = "vision" if actual_b64 else "coding"
                logger.warning(f"[answer] {label} model failed ({e}). Falling back to chat model...")
                return self.ai_provider.generate(context, system_prompt=system_prompt, base64_image=None)
            raise

    def _stream_with_fallback(self, context, system_prompt, b64, mode):
        """
        Streams chunks live (no buffering). If the specialised provider errors
        before the first chunk arrives, falls back to the chat model transparently.
        If it errors mid-stream we just stop — a partial answer is better than a crash.
        """
        provider = self._pick_provider(b64, mode)
        actual_b64 = b64 if provider is getattr(self, 'ai_vision_provider', None) else None
        gen = provider.generate_stream(context, system_prompt=system_prompt, base64_image=actual_b64)
        
        # Pull the very first chunk inside a try so we can catch pre-stream errors
        # (e.g. model not found, 400 Bad Request) and fall back cleanly
        first_chunk = None
        try:
            first_chunk = next(gen)
        except StopIteration:
            return  # empty response
        except Exception as e:
            if provider is not self.ai_provider:
                label = "vision" if actual_b64 else "coding"
                logger.warning(f"[answer] {label} model failed before first chunk ({e}). Falling back to chat model...")
                for chunk in self.ai_provider.generate_stream(context, system_prompt=system_prompt, base64_image=None):
                    yield chunk
                return
            raise

        # First chunk arrived — yield it and then stream the rest live
        yield first_chunk
        try:
            for chunk in gen:
                yield chunk
        except Exception as e:
            logger.warning(f"[answer] Stream interrupted mid-way ({e}). Partial answer delivered.")

    def generate_answer(self, intent_val: str, session_context: List[ConversationTurn]) -> AnswerResult:
        start_time = time.time()
        
        if not session_context:
            return AnswerResult(success=False, answer_text="", answer_mode=AnswerMode.GENERAL, error="Empty session context")
            
        last_turn = session_context[-1]
        
        has_context = bool(
            self.context_manager.current_context.interview.role or 
            self.context_manager.current_context.interview.company or
            self.context_manager.current_context.interview.company_details or
            self.context_manager.current_context.interview.important_info or
            self.context_manager.current_context.personal.name or
            self.context_manager.current_context.personal.education or
            self.context_manager.current_context.personal.skills or
            self.context_manager.current_context.personal.projects or
            self.context_manager.current_context.personal.resume_text
        )
        
        request = AnswerRequest(
            user_text=last_turn.text,
            intent=intent_val,
            session_turns=len(session_context),
            has_context=has_context
        )
        
        mm_ctx = None
        if self.mm_engine:
            mm_ctx = self.mm_engine.build_context(last_turn.text, len(session_context))
        
        mode = self._determine_mode(request, mm_ctx)
        logger.info(f"[answer] Selected mode: {mode.value}")
        
        system_prompt = self._build_system_prompt(mode, mm_ctx, user_text=last_turn.text)
        
        # Trim context to max_turns
        trimmed_context = session_context[-self.max_context_turns:]
        
        # Web Search Integration
        from app.core.config import load_config
        config = load_config()
        if config.enable_web_search:
            text_lower = request.user_text.lower()
            if any(w in text_lower for w in ["latest", "current", "news", "today", "now", "recent", "update", "2025", "2026"]):
                logger.info("[answer] Real-time keywords detected, executing web search...")
                from app.ai.tools import search_web
                search_results = search_web(request.user_text, max_results=3)
                system_prompt += f"\n\n{search_results}"
                
        # Hint Mode
        if config.hint_mode_active:
            system_prompt += "\n\nHINT MODE ACTIVE: Provide exactly 1-3 extremely short bullet points (max 10 words each). Do NOT provide full paragraphs or complete code solutions. Give conceptual hints only."
                
        try:
            b64 = mm_ctx.base64_image if mm_ctx else None
            ai_resp = self._generate_with_fallback(trimmed_context, system_prompt, b64, mode)
            latency = time.time() - start_time
            return AnswerResult(
                success=True,
                answer_text=ai_resp.text,
                answer_mode=mode,
                latency=latency
            )
        except Exception as e:
            logger.error(f"[answer] Error generating answer: {e}")
            
            error_msg = str(e)
            user_facing = f"I couldn't generate an answer right now ({error_msg})."
            if "429" in error_msg:
                user_facing = "I couldn't reach the AI service right now due to rate limiting (HTTP 429). Please try again shortly."
            elif "401" in error_msg or "403" in error_msg:
                user_facing = "I couldn't authenticate with the AI service. Please check your API key in settings."
                
            return AnswerResult(
                success=False,
                answer_text=user_facing,
                answer_mode=mode,
                latency=time.time() - start_time,
                error=error_msg
            )

    def generate_answer_stream(self, intent_val: str, session_context: List[ConversationTurn]):
        if not session_context:
            yield "Error: Empty session context"
            return
            
        last_turn = session_context[-1]
        
        has_context = bool(
            self.context_manager.current_context.interview.role or 
            self.context_manager.current_context.interview.company or
            self.context_manager.current_context.personal.name or
            self.context_manager.current_context.personal.resume_text
        )
        
        request = AnswerRequest(
            user_text=last_turn.text,
            intent=intent_val,
            session_turns=len(session_context),
            has_context=has_context
        )
        
        mm_ctx = None
        if self.mm_engine:
            mm_ctx = self.mm_engine.build_context(last_turn.text, len(session_context))
        
        mode = self._determine_mode(request, mm_ctx)
        logger.info(f"[answer] Selected mode for stream: {mode.value}")
        
        system_prompt = self._build_system_prompt(mode, mm_ctx, user_text=last_turn.text)
        trimmed_context = session_context[-self.max_context_turns:]
        
        from app.core.config import load_config
        config = load_config()
        if config.enable_web_search:
            text_lower = request.user_text.lower()
            if any(w in text_lower for w in ["latest", "current", "news", "today", "now", "recent", "update", "2025", "2026"]):
                logger.info("[answer] Real-time keywords detected, executing web search...")
                from app.ai.tools import search_web
                search_results = search_web(request.user_text, max_results=3)
                system_prompt += f"\n\n{search_results}"
                
        if config.hint_mode_active:
            system_prompt += "\n\nHINT MODE ACTIVE: Provide exactly 1-3 extremely short bullet points (max 10 words each). Do NOT provide full paragraphs or complete code solutions. Give conceptual hints only."
                
        try:
            b64 = mm_ctx.base64_image if mm_ctx else None
            for chunk in self._stream_with_fallback(trimmed_context, system_prompt, b64, mode):
                yield chunk
        except Exception as e:
            logger.error(f"[answer] Error generating stream: {e}")
            yield f" [Error: {e}]"
