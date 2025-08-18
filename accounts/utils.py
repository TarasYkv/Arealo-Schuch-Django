from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import urlencode


def redirect_with_params(view_name, **params):
    """Helper function to redirect with query parameters.

    Usage:
        return redirect_with_params('accounts:company_info', tab='bug_chat')
    """
    url = reverse(view_name)
    if params:
        url = f"{url}?{urlencode(params)}"
    return redirect(url)
