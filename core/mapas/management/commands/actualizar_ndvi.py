from datetime import date, timedelta

from django.core.management.base import BaseCommand

from gestion_agro.models import Campo
from mapas.aux_sentenial import _get_sh_config, procesar_campo
from mapas.models import CapturaSatelite


class Command(BaseCommand):
    help = "Descarga NDVI desde Sentinel-2 para todos los campos activos (o uno específico)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--campo-id", type=int, default=None,
            help="Procesar solo el campo con este ID",
        )
        parser.add_argument(
            "--dias", type=int, default=5,
            help="Ventana de días hacia atrás desde hoy para buscar imagen (default: 5)",
        )
        parser.add_argument(
            "--forzar", action="store_true",
            help="Forzar reprocesado aunque ya exista captura reciente",
        )

    def handle(self, *args, **options):
        try:
            config = _get_sh_config()
        except RuntimeError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        campo_id = options["campo_id"]
        dias     = options["dias"]
        forzar   = options["forzar"]

        if campo_id:
            campos = Campo.objects.filter(id=campo_id)
            if not campos.exists():
                self.stderr.write(self.style.ERROR(f"Campo {campo_id} no encontrado"))
                return
        else:
            # Solo campos con contorno o áreas definidas
            campos = Campo.objects.filter(ciclos__activa=True).distinct()

        fecha_hasta = date.today()

        for campo in campos:
            self.stdout.write(f"\nCampo: {campo.nombre} (id={campo.id})")

            ultima = (
                CapturaSatelite.objects
                .filter(campo=campo, fuente="sentinel2", estado="procesada")
                .order_by("-fecha")
                .first()
            )

            if ultima and not forzar:
                fecha_desde = ultima.fecha + timedelta(days=1)
                if fecha_desde > fecha_hasta:
                    self.stdout.write(
                        f"  OK — última captura: {ultima.fecha}. Sin imágenes nuevas."
                    )
                    continue
            else:
                fecha_desde = fecha_hasta - timedelta(days=dias)

            self.stdout.write(f"  Ventana: {fecha_desde} → {fecha_hasta}")

            try:
                procesar_campo(campo, fecha_desde, fecha_hasta, config, self.stdout)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  ERROR: {e}"))

        self.stdout.write(self.style.SUCCESS("\nProceso finalizado."))
