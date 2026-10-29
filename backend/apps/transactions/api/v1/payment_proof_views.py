# -*- coding: utf-8 -*-
"""客户上传电汇付款凭证（2026-10-29）。

## 为什么要有这一步

产品已经支持 PO + 电汇，但**客户汇完款只能发邮件告诉我们**，运营再手工去
「开票台 → Record Payment」录入。中间全靠邮件，容易漏、且客户不知道"我传的凭证
你们收到没有"。

`PaymentRecord.proof_file` 字段和 `PaymentProofSerializer` **早就写好了，但没有任何
端点使用它们**（2026-10-29 实测：全仓 grep 只有定义处）。这一步就是把缺的那一环补上。

## 流程

    运营开票（invoice issued）
      → 客户汇款
      → 客户在这里上传凭证（本端点，status=PENDING）
      → 运营在开票台核验（POST /admin/invoices/<id>/verify-payment）
      → 发票转 paid、订单转 paid

## 三条刻意的约束

1. **客户端只能建 PENDING，不能建 VERIFIED。**
   钱到没到账只有财务知道。"客户说我汇了"不等于"钱到了"，必须人工核验。
   运营手工录入走的是另一个端点（`/invoices/<id>/pay/`），那条直接写 VERIFIED ——
   因为那是运营自己在核对完银行流水之后的操作。

2. **只认自己的发票。** `order__user=request.user` 直接写进 `get_object_or_404`，
   别人的发票返回 404 而不是 403 —— 不泄露"这个 id 存在"。

3. **同一张发票同时只允许一条 PENDING。**
   否则客户反复点提交会堆出一串待核验记录，运营分不清哪条是最终版。
   被 rejected 之后可以重新传（那时已经不是 PENDING 了）。
"""
import os

from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.mixins import EnvelopeMixin
from apps.transactions.models import Invoice, PaymentRecord
from apps.transactions.api.v1.serializers import (
    PaymentProofSerializer, PaymentRecordSerializer,
)

#: 只收这几种：PDF 是银行回单最常见的格式，图片是手机截图。
ALLOWED_EXT = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_PROOF_BYTES = 10 * 1024 * 1024  # 10MB，与 PO 附件上限一致


class InvoicePaymentProofView(EnvelopeMixin, APIView):
    """POST /api/v1/invoices/<id>/payment-proof/  (multipart/form-data)

    body: proof_file=<file>  amount=<decimal>  reference=<bank ref>  notes=<optional>
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related('order'), pk=pk, order__user=request.user)

        # 只有「已开票 / 逾期」才谈得上付款。draft=还没开票；paid=已付清；void=作废。
        if invoice.status not in (Invoice.Status.ISSUED, Invoice.Status.OVERDUE):
            return self.error_response(
                f'Invoice is {invoice.status}; payment proof is only accepted for '
                'issued / overdue invoices.',
                code='INVOICE_NOT_PAYABLE', status_code=400)

        if PaymentRecord.objects.filter(
                invoice=invoice, status=PaymentRecord.Status.PENDING).exists():
            return self.error_response(
                'A payment proof for this invoice is already awaiting verification. '
                'Please wait for our team to confirm it.',
                code='PROOF_PENDING_EXISTS', status_code=409)

        upload = request.FILES.get('proof_file')
        if not upload:
            return self.error_response(
                'proof_file is required', code='VALIDATION_ERROR', status_code=400)
        ext = os.path.splitext(upload.name or '')[1].lower()
        if ext not in ALLOWED_EXT:
            return self.error_response(
                f'Unsupported file type "{ext}". Allowed: {", ".join(sorted(ALLOWED_EXT))}',
                code='BAD_FILE_TYPE', status_code=400)
        if (upload.size or 0) > MAX_PROOF_BYTES:
            return self.error_response(
                f'File too large ({upload.size} bytes); limit is 10 MB',
                code='FILE_TOO_LARGE', status_code=400)

        ser = PaymentProofSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        amount = ser.validated_data['amount']

        # 允许部分付款（<= balance_due），但不允许超额申报 —— 超额一定录错了，
        # 让它进待核验队列只会让财务多核对一遍。
        if amount <= 0:
            return self.error_response(
                'amount must be positive', code='VALIDATION_ERROR', status_code=400)
        if amount > invoice.balance_due:
            return self.error_response(
                f'amount {amount} exceeds the outstanding balance {invoice.balance_due}',
                code='AMOUNT_EXCEEDS_BALANCE', status_code=400)

        payment = PaymentRecord.objects.create(
            invoice=invoice,
            method=PaymentRecord.Method.WIRE,
            amount=amount,
            currency=invoice.currency,
            reference=ser.validated_data.get('reference', '') or '',
            notes=ser.validated_data.get('notes', '') or '',
            proof_file=upload,
            # 客户端永远只能建 PENDING：见模块 docstring 第 1 条
            status=PaymentRecord.Status.PENDING,
        )
        return self.success_response(
            PaymentRecordSerializer(payment).data,
            meta={'message': 'Received. Our team will verify it shortly.'},
        )
