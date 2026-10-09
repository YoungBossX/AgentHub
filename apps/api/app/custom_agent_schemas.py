from pydantic import BaseModel, ConfigDict, Field


class CustomAgentRequest(BaseModel):
    display_name: str = Field(alias="displayName", max_length=80)
    mention_alias: str = Field(alias="mentionAlias", max_length=64)
    role: str
    provider_id: str = Field(alias="providerId")
    tool_policy: str = Field(alias="toolPolicy")
    supported_targets: list[str] = Field(alias="supportedTargets")
    capability_tags: list[str] = Field(alias="capabilityTags")
    system_prompt: str = Field(default="", alias="systemPrompt", max_length=8000)
    description: str = Field(default="", max_length=1000)
    avatar_initials: str = Field(default="", alias="avatarInitials", max_length=3)
    enabled: bool = True

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
