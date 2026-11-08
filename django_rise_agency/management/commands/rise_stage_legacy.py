import hashlib
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_rise_agency.models import RiseLegacySnapshot
from django_rise_agency.legacy_validation import audit


class Command(BaseCommand):
    help = 'Valida e copia um JSON WP para uma zona de staging. NÃO migra para tabelas BrightBean.'

    def add_arguments(self, parser):
        parser.add_argument('input', type=Path)
        parser.add_argument('--apply', action='store_true', help='Persistir em staging (por defeito simulação).')

    def handle(self, *args, **options):
        try:
            content = json.loads(options['input'].read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError(f'Ficheiro inválido: {exc}')
        if content.get('metadata', {}).get('schema') != 'rise-wordpress-1.11-export-v1':
            raise CommandError('Exportação não reconhecida.')
        result = audit(content)
        if not result["ok"]:
            raise CommandError("Exportação falhou validação: " + "; ".join(result["errors"][:5]))
        rows = [(table, row) for table, entries in content["tables"].items() for row in entries]
        rows = [(table, row) for table, row in rows if table != 'records' or row.get('kind') != 'integrations']
        self.stdout.write(f'{len(rows)} registos lidos. Modo: {"staging" if options["apply"] else "simulação"}')
        if not options['apply']:
            return
        inserted = 0
        with transaction.atomic():
            for table, row in rows:
                rid = int(row['id'])
                serialised = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
                digest = hashlib.sha256(serialised.encode('utf-8')).hexdigest()
                instance, created = RiseLegacySnapshot.objects.get_or_create(
                    source_table=table, source_id=rid,
                    defaults={
                        'source_client_id': int(row.get('client_id') or 0),
                        'source_kind': row.get('kind','') if table == 'records' else '',
                        'checksum_sha256': digest, 'snapshot': row,
                    }
                )
                if not created and instance.checksum_sha256 != digest:
                    raise CommandError(f'Conflito em {table}#{rid}: conteúdo diferente. Não é feita substituição automática.')
                inserted += created
        self.stdout.write(self.style.SUCCESS(f'{inserted} registos inseridos; nada alterado nas tabelas BrightBean.'))
