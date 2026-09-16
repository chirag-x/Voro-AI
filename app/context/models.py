from pydantic import BaseModel, Field
from typing import List

class InterviewContextModel(BaseModel):
    role: str = ""
    company: str = ""
    company_details: str = ""
    important_info: str = ""
    interview_type: str = ""
    technology_stack: List[str] = Field(default_factory=list)

class PersonalKnowledgeModel(BaseModel):
    name: str = ""
    education: str = ""
    projects: str = ""
    skills: List[str] = Field(default_factory=list)
    resume_text: str = ""

class FullContext(BaseModel):
    interview: InterviewContextModel = Field(default_factory=InterviewContextModel)
    personal: PersonalKnowledgeModel = Field(default_factory=PersonalKnowledgeModel)
