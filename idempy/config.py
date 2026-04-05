from tying import any 
from dataclasses import dataclass

@dataclass
class Config: 
    """app config"""
    app_name: str = "idempy"

