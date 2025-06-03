from django.shortcuts import render

# Create your views here.
def rechnerAnsicht(request):
    return render(request, 'rechner.html')