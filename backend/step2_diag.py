# 增强诊断：打印 settings 实际配置 + 尝试 import
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.conf import settings
print("INSTALLED_APPS:", settings.INSTALLED_APPS)
print("DATABASES:", settings.DATABASES)
from django.apps import apps
print("apps.ready:", apps.ready, "num_models:", len(list(apps.get_models())))
try:
    from apps.knowledge.models import Protocol
    print("Protocol OK count=", Protocol.objects.count())
except Exception as e:
    print("Protocol FAIL:", repr(e))
try:
    from apps.commerce.models import Product
    print("commerce.Product OK count=", Product.objects.count())
except Exception as e:
    print("commerce.Product FAIL:", repr(e))
try:
    from apps.commerce_products.models import Product as P2
    print("commerce_products.Product OK count=", P2.objects.count())
except Exception as e:
    print("commerce_products.Product FAIL:", repr(e))
