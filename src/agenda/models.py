from django.db import models

class Bloque(models.Model):
    id = models.AutoField(primary_key=True)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_final = models.TimeField()
    disponible = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.fecha} {self.hora_inicio}-{self.hora_final}"
