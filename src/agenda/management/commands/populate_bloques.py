from django.core.management.base import BaseCommand
from agenda.models import Bloque
from datetime import date, time, timedelta
import random

class Command(BaseCommand):
    help = 'Rellenando agenda con bloques dummy para 2026'

    def handle(self, *args, **options):
        start_date = date(2026, 3, 1)
        end_date = date(2026, 12, 31)
        
        delta = end_date - start_date
        
        Bloque.objects.filter(fecha__year=2026).delete()
        
        count = 0
        for i in range(delta.days + 1):
            day = start_date + timedelta(days=i)
            
            slots = [
                (time(9, 0), time(11, 0)),
                (time(11, 0), time(13, 0)),
                (time(14, 0), time(16, 0)),
                (time(16, 0), time(18, 0)),
            ]
            
            for start, end in slots:
                Bloque.objects.create(
                    fecha=day,
                    hora_inicio=start,
                    hora_final=end,
                    disponible=random.choice([True, False])
                )
                count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Creados {count} bloque para el 2026'))
