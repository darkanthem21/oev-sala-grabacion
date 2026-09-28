from django.core.exceptions import ValidationError
from django.db import models


class Bloque(models.Model):
    id = models.AutoField(primary_key=True)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_final = models.TimeField()
    disponible = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(hora_inicio__lt=models.F("hora_final")),
                name="bloque_hora_inicio_anterior_hora_final",
            )
        ]

    def clean(self):
        super().clean()
        if self.hora_inicio and self.hora_final and self.hora_inicio >= self.hora_final:
            raise ValidationError({"hora_final": "La hora final debe ser posterior a la hora de inicio."})

        if self.fecha and self.hora_inicio and self.hora_final:
            solapados = Bloque.objects.filter(
                fecha=self.fecha,
                hora_inicio__lt=self.hora_final,
                hora_final__gt=self.hora_inicio,
            )
            if self.pk:
                solapados = solapados.exclude(pk=self.pk)
            if solapados.exists():
                raise ValidationError("Ya existe un bloque en este horario que se solapa con el propuesto.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.fecha} {self.hora_inicio}-{self.hora_final}"

