from django.shortcuts import redirect
from django.urls import reverse


def redirect_with_params(view_name, **params):
    """
    Helper function to redirect with query parameters
    
    Usage:
        return redirect_with_params('accounts:company_info', tab='bug_chat')
    """
    url = reverse(view_name)
    if params:
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        url = f'{url}?{query_string}'
    return redirect(url)