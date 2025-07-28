# Mail App Views Package
from .mail_views import (
    MailModernView,
    MailSimpleView, 
    MailStandaloneView,
    MailTicketsView,
    ToggleEmailStatusView,
    CloseTicketView,
    EmailContentAPIView
)

__all__ = [
    'MailModernView',
    'MailSimpleView',
    'MailStandaloneView', 
    'MailTicketsView',
    'ToggleEmailStatusView',
    'CloseTicketView',
    'EmailContentAPIView'
]