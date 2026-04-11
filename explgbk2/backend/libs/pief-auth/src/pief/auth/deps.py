"""FastAPI typed dependency aliases for pief.auth."""

from typing import Annotated

import openfga_sdk
from fastapi import Depends

from pief.auth.client import get_fga_client

FGAClientDep = Annotated[openfga_sdk.OpenFgaClient, Depends(get_fga_client)]
