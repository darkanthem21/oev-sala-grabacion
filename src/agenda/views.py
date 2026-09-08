import calendar
from django.shortcuts import render
from datetime import datetime
from .models import Bloque

class AgendaCalendar(calendar.HTMLCalendar):
    def __init__(self, bloques):
        super().__init__()
        self.bloques = {b.fecha.day for b in bloques}

    def formatday(self, day, weekday):
        if day == 0:
            return '<td class="noday">&nbsp;</td>'
        
        css_class = self.cssclasses[weekday]
        if day in self.bloques:
            css_class += ' available'
            return f'<td class="{css_class}"><a href="#">{day}</a></td>'
        
        return f'<td class="{css_class}">{day}</td>'

def calendario(request):
    ahora = datetime.now()
    year = ahora.year
    month = ahora.month

    bloques = Bloque.objects.filter(fecha__year=year, fecha__month=month, disponible=True)
    
    cal = AgendaCalendar(bloques)
    html_cal = cal.formatmonth(year, month)

    return render(request, "agenda/calendario.html", {
        "calendario": html_cal,
    })
