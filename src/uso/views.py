from django.shortcuts import render


def checklist(request):
    return render(request, "uso/checklist.html")