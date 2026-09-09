from pydantic import Field, BaseModel


class GroupRequest(BaseModel):
    
    group_id: str = Field(...,
                          alias='groupId',
                          description="Unique identifier for the group",
                          examples=["my-group-123", "team-alpha"],
                          min_length=1,
                          max_length=255
                          )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"groupId": "my-group-123"},
                {"groupId": "team-alpha-prod"},
            ]
        }
    }

