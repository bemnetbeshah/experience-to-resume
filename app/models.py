"""Validated contracts shared by every pipeline stage."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class JobAnalysis(BaseModel):
    role_title: str
    company: Optional[str]
    required_skills: list[str]
    preferred_skills: list[str]
    responsibilities: list[str]
    keywords: list[str]
    resume_angle: str


class ContactLink(BaseModel):
    label: str
    url: str


class Contact(BaseModel):
    name: str
    email: str
    phone: str
    location: str
    links: list[ContactLink]


class EducationItem(BaseModel):
    institution: str
    degree: str
    location: str
    start: str
    end: str
    highlights: list[str]


class CandidateProfile(BaseModel):
    contact: Contact
    summary: str
    education: list[EducationItem]
    achievements: list[str]


class ProfileItem(BaseModel):
    id: str
    title: str
    category: str
    organization: Optional[str]
    location: Optional[str]
    start: Optional[str]
    end: Optional[str]
    url: Optional[str]
    bullets: list[str]
    tags: list[str]


class RetrievedProfile(BaseModel):
    candidate: CandidateProfile
    items: list[ProfileItem]
    skills: dict[str, list[str]]


class ResumePlan(BaseModel):
    summary_angle: str
    featured_item_ids: list[str]
    additional_item_ids: list[str]
    skills_to_show: list[str]
    sections_order: list[str]

    @property
    def selected_item_ids(self) -> list[str]:
        return [*self.featured_item_ids, *self.additional_item_ids]


class ResumeBullet(BaseModel):
    text: str
    source_item_id: str


class ResumeSection(BaseModel):
    section_name: str
    item_title: str
    organization: Optional[str]
    location: Optional[str]
    date_range: Optional[str]
    url: Optional[str]
    bullets: list[ResumeBullet]
    layout: Literal["full", "compact"] = "full"


class ResumeContent(BaseModel):
    headline: str
    summary: str
    skills: list[str]
    sections: list[ResumeSection]


class ResumeDraft(BaseModel):
    name: str
    email: str
    phone: str
    location: str
    links: list[ContactLink]
    headline: str
    summary: str
    education: list[EducationItem]
    skills: list[str]
    sections: list[ResumeSection]
    achievements: list[str] = Field(default_factory=list)


class ResumeCritique(BaseModel):
    satisfied: bool
    fit_action: Literal["trim", "expand", "ok"]
    issues: list[str]
    suggestions: list[str]
