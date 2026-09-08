import calendar
from django.shortcuts import render
from datetime import datetime
from .models import Bloque

class AgendaCalendar(calendar.HTMLCalendar):
    def __init__(self, bloques, year, month):
        super().__init__()
        self.bloques = {b.fecha.day for b in bloques}
        self.year = year
        self.month = month

    def formatday(self, day, weekday):
        if day == 0:
            return '<td class="noday">&nbsp;</td>'
        
        css_class = self.cssclasses[weekday]
        if day in self.bloques:
            css_class += ' available'
            date_str = f"{self.year}-{self.month:02d}-{day:02d}"
            return f'<td class="{css_class}" data-date="{date_str}">{day}</td>'
        
        return f'<td class="{css_class}">{day}</td>'

def calendario(request):
    ahora = datetime.now()
    year = ahora.year
    month = ahora.month

    bloques = Bloque.objects.filter(fecha__year=year, fecha__month=month, disponible=True)
    
    cal = AgendaCalendar(bloques, year, month)
    html_cal = cal.formatmonth(year, month)

    return render(request, "agenda/calendario.html", {
        "calendario": html_cal,
    })