from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, model_validator

Role = Literal['ceo','cfo','treasury','accountant']
class NewsInput(BaseModel):
    title: str = Field(default='',max_length=500)
    text: str = Field(default='',max_length=60000)
    url: HttpUrl | None = None
    published_at: datetime | None = None
    @model_validator(mode='after')
    def content(self):
        if not self.url and (len(self.text.strip()) < 30 or len(self.title.strip()) < 5):
            raise ValueError('Укажите URL или заголовок от 5 символов и текст от 30 символов')
        return self
class AnalysisInput(BaseModel):
    company_id: str = Field(min_length=1,max_length=100)
    article_id: str = Field(min_length=1,max_length=64)
    role: Role = 'cfo'
class QuestionInput(BaseModel):
    question: str = Field(min_length=5,max_length=2000)
class FeedbackInput(BaseModel):
    rating: Literal[-1,1]
    comment: str = Field(default='',max_length=2000)
class EvidenceQuote(BaseModel):
    evidence_id: str = Field(min_length=1,max_length=150)
    quote: str = Field(min_length=8,max_length=700)

class Claim(BaseModel):
    text: str = Field(min_length=1,max_length=1800)
    evidence_ids: list[str] = Field(min_length=1,max_length=8)
    evidence_quotes: list[EvidenceQuote] = Field(default_factory=list,max_length=8)
class GeneratedInsight(BaseModel):
    summary: Claim
    risks: list[Claim] = Field(max_length=6)
    opportunities: list[Claim] = Field(max_length=6)
    actions: list[Claim] = Field(max_length=6)
    bank_view: list[Claim] = Field(default_factory=list,max_length=4)
    uncertainties: list[str] = Field(max_length=12)
