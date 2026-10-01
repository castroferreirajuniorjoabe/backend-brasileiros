from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class HousingAdCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: str
    phone: str
    city: str
    property_type: str
    living_preference: str
    
    # Checkboxes opcionais
    accepts_pets: bool = False
    accepts_children: bool = False
    is_420_friendly: bool = False
    is_quiet_environment: bool = False
    accepts_smokers: bool = False
    accepts_couples: bool = False
    accepts_visitors: bool = False
    accepts_home_office: bool = False
    
    # Extras
    announcer_identity: Optional[str] = None
    charges_included: Optional[bool] = None
    deposit: Optional[str] = None
    surface_m2: Optional[int] = None
    floor: Optional[int] = None
    furnished: Optional[bool] = None
    roommates_count: Optional[int] = None
    roommates_profile: Optional[str] = None
    house_rules: Optional[str] = None
    documents_required: Optional[List[str]] = None
    min_stay: Optional[str] = None
    
    availability_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_unlimited: bool = False
    
    virtual_tour_link: Optional[str] = None

class HousingMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    sender_name: str
    sender_email: str
    sender_phone: Optional[str] = None
