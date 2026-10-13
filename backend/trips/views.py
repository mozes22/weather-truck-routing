from rest_framework.decorators import api_view
from rest_framework.response import Response


# @api_view turns a plain function into an API view that only accepts GET.
@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})
