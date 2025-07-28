from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="templates")

@router.get("/calendar", response_class=HTMLResponse)
async def get_calendar(request: Request):
    return templates.TemplateResponse("calendar.html", {"request": request})