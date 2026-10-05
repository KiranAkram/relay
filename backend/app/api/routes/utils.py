from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pydantic.networks import EmailStr

from app.api.deps import get_current_active_superuser
from app.core.config import settings
from app.models import Message
from app.utils import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check/")
async def health_check() -> bool:
    return True


class DemoAccess(BaseModel):
    email: str
    password: str


@router.get("/demo-access/", response_model=DemoAccess | None)
def demo_access() -> DemoAccess | None:
    """
    The demo doctor login for the sign-in page. Null unless DEMO_ACCESS_BANNER
    is on and the demo account is configured.
    """
    if not (
        settings.DEMO_ACCESS_BANNER
        and settings.DEMO_DOCTOR_EMAIL
        and settings.DEMO_DOCTOR_PASSWORD
    ):
        return None
    return DemoAccess(
        email=settings.DEMO_DOCTOR_EMAIL, password=settings.DEMO_DOCTOR_PASSWORD
    )
