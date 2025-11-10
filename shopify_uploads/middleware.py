"""
Middleware to prevent redirects for Shopify Upload API endpoints.

CORS preflight requests (OPTIONS) fail if there's a redirect from workloom.de to www.workloom.de.
This middleware disables the redirect for API endpoints.
"""


class DisableRedirectForAPIMiddleware:
    """
    Middleware to disable automatic redirects for API endpoints.
    Must be placed BEFORE CommonMiddleware in settings.MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if this is an API request
        if request.path.startswith('/shopify-uploads/api/'):
            # Disable redirect by setting the HOST header to match www.workloom.de
            # This prevents CommonMiddleware from redirecting
            if request.get_host() == 'workloom.de':
                request.META['HTTP_HOST'] = 'www.workloom.de'

        response = self.get_response(request)
        return response
