import json
import os
from app.context.models import FullContext
from app.utils.logging import logger

class ContextManager:
    """Manages local storage and loading of interview and personal context via profiles."""
    def __init__(self, storage_path: str = None):
        if storage_path is None:
            # Use AppData so profiles survive app uninstalls and auto-updates
            appdata = os.getenv("APPDATA", os.path.expanduser("~"))
            storage_dir = os.path.join(appdata, "Norvi", "Voro")
            os.makedirs(storage_dir, exist_ok=True)
            self.storage_path = os.path.join(storage_dir, "profiles.json")
        else:
            self.storage_path = storage_path
            
        self.profiles = {"Default": FullContext()}
        self.active_profile_name = "Default"
        self.load()

    @property
    def current_context(self) -> FullContext:
        return self.profiles[self.active_profile_name]

    def load(self):
        legacy_path = "context.json"
        
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active_profile_name = data.get("active_profile", "Default")
                    self.profiles = {}
                    for k, v in data.get("profiles", {}).items():
                        self.profiles[k] = FullContext.model_validate(v)
                    
                    if self.active_profile_name not in self.profiles:
                        self.profiles[self.active_profile_name] = FullContext()
                logger.info("Profiles loaded successfully.")
                return
            except Exception as e:
                logger.error(f"Failed to load profiles (corrupted?): {e}")
                self.profiles = {"Default": FullContext()}
                self.active_profile_name = "Default"
                
        # Fallback to legacy context.json
        if os.path.exists(legacy_path):
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.profiles["Default"] = FullContext.model_validate(data)
                logger.info("Migrated legacy context.json to profiles.json.")
            except Exception:
                pass
                
        if "Default" not in self.profiles:
            self.profiles["Default"] = FullContext()

    def save(self):
        try:
            data = {
                "active_profile": self.active_profile_name,
                "profiles": {k: v.model_dump() for k, v in self.profiles.items()}
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.info("Profiles saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
            
    def create_profile(self, name: str):
        if name and name not in self.profiles:
            self.profiles[name] = FullContext()
            self.save()

    def delete_profile(self, name: str):
        if name in self.profiles and len(self.profiles) > 1:
            del self.profiles[name]
            if self.active_profile_name == name:
                self.active_profile_name = list(self.profiles.keys())[0]
            self.save()

    def switch_profile(self, name: str):
        if name in self.profiles:
            self.active_profile_name = name
            self.save()

    def update_interview(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.current_context.interview, k):
                setattr(self.current_context.interview, k, v)
        self.save()

    def update_personal(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.current_context.personal, k):
                setattr(self.current_context.personal, k, v)
        self.save()

    def reset(self):
        self.profiles[self.active_profile_name] = FullContext()
        self.save()
        logger.info(f"[context] Profile '{self.active_profile_name}' reset")

    def build_system_prompt_addition(self, user_query: str = "") -> str:
        """Returns a formatted string of the context for the Answer Engine."""
        parts = []
        
        # Interview Context
        if any([self.current_context.interview.role, self.current_context.interview.company, self.current_context.interview.technology_stack, self.current_context.interview.company_details, self.current_context.interview.important_info]):
            parts.append("--- INTERVIEW / COMPANY CONTEXT ---")
            if self.current_context.interview.role:
                parts.append(f"Role: {self.current_context.interview.role}")
            if self.current_context.interview.company:
                parts.append(f"Company: {self.current_context.interview.company}")
            if self.current_context.interview.company_details:
                parts.append(f"Company Details: {self.current_context.interview.company_details}")
            if self.current_context.interview.interview_type:
                parts.append(f"Type: {self.current_context.interview.interview_type}")
            if self.current_context.interview.technology_stack:
                parts.append(f"Tech Stack: {', '.join(self.current_context.interview.technology_stack)}")
            if self.current_context.interview.important_info:
                parts.append(f"Important Info:\n{self.current_context.interview.important_info}")
                
        # Personal Knowledge
        if any([self.current_context.personal.name, self.current_context.personal.education, self.current_context.personal.projects, self.current_context.personal.skills, self.current_context.personal.resume_text]):
            parts.append("--- USER PROFILE & KNOWLEDGE ---")
            if self.current_context.personal.name:
                parts.append(f"Name: {self.current_context.personal.name}")
            if self.current_context.personal.education:
                parts.append(f"Education: {self.current_context.personal.education}")
            if self.current_context.personal.skills:
                parts.append(f"Skills: {', '.join(self.current_context.personal.skills)}")
            
            # RAG processing for projects and resume
            kb_chunks = []
            if self.current_context.personal.projects:
                kb_chunks.append(f"Projects:\n{self.current_context.personal.projects}")
                
            if self.current_context.personal.resume_text:
                # Naive chunking by paragraphs for the resume
                paragraphs = [p.strip() for p in self.current_context.personal.resume_text.split('\n\n') if len(p.strip()) > 50]
                if not paragraphs:
                    paragraphs = [self.current_context.personal.resume_text[:2000]] # Fallback
                kb_chunks.extend(paragraphs)
                
            if kb_chunks:
                if len(kb_chunks) <= 3:
                    # If small enough, include all
                    parts.append("Resume/Bio Notes:\n" + "\n\n".join(kb_chunks))
                else:
                    # RAG Retrieval
                    from app.context.rag import SimpleBM25
                    rag = SimpleBM25()
                    rag.fit(kb_chunks)
                    top_chunks = rag.get_top_k(user_query, k=2)
                    
                    if not top_chunks:
                        # Fallback to first 2 chunks if query didn't match anything
                        top_chunks = kb_chunks[:2]
                        
                    parts.append("Relevant Resume/Bio Snippets (Retrieved via RAG):\n" + "\n\n".join(top_chunks))
                
        if parts:
            parts.insert(0, "This is your (the candidate's) background and context for this interview. Use this to construct your first-person answers when relevant:")
            return "\n".join(parts)
        
        return ""
