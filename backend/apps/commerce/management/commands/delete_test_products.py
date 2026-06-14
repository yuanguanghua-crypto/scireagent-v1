"""Delete test products (names containing '[TEST]')."""
from django.core.management.base import BaseCommand
from apps.commerce.models import Product, SKU, ProductDocument
from apps.bridges.models import ProductMethod, ProductReference, ProductCompatibility, ProductProduct


class Command(BaseCommand):
    help = 'Delete all test products (names containing [TEST])'

    def handle(self, *args, **options):
        test_products = Product.objects.filter(name__icontains='[TEST]')
        count = test_products.count()

        if count == 0:
            self.stdout.write(self.style.WARNING('No test products found.'))
            return

        self.stdout.write(f'Found {count} test products:')
        for p in test_products:
            self.stdout.write(f'  - {p.name} (id={p.id}, status={p.status})')

        # Confirm
        confirm = input(f'\nDelete {count} test products and all related data? [y/N]: ')
        if confirm.lower() != 'y':
            self.stdout.write(self.style.NOTICE('Cancelled.'))
            return

        test_ids = list(test_products.values_list('id', flat=True))

        # Delete related data first
        deleted = {}
        deleted['ProductMethods'] = ProductMethod.objects.filter(product_id__in=test_ids).delete()[0]
        deleted['ProductReferences'] = ProductReference.objects.filter(product_id__in=test_ids).delete()[0]
        deleted['ProductCompatibility'] = ProductCompatibility.objects.filter(source_product_id__in=test_ids).delete()[0] + ProductCompatibility.objects.filter(target_product_id__in=test_ids).delete()[0]
        deleted['ProductProduct'] = ProductProduct.objects.filter(source_product_id__in=test_ids).delete()[0] + ProductProduct.objects.filter(target_product_id__in=test_ids).delete()[0]
        deleted['SKUs'] = SKU.objects.filter(product_id__in=test_ids).delete()[0]
        deleted['Documents'] = ProductDocument.objects.filter(product_id__in=test_ids).delete()[0]

        # Delete products
        deleted['Products'] = test_products.delete()[0]

        self.stdout.write(self.style.SUCCESS(f'\nDeleted:'))
        for model, count in deleted.items():
            if count > 0:
                self.stdout.write(f'  {model}: {count}')
        self.stdout.write(self.style.SUCCESS(f'\nDone! {count} test products removed.'))
