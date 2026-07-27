"""SuperAdmin: filial so'rovlari.

Ilgari bu so'rovlarni faqat Telegram bot orqali tasdiqlash mumkin edi —
panelda ular umuman ko'rinmasdi. Bot ishlamay qolsa yoki xabar o'chib
ketsa, so'rov "osilib" qolardi. Endi shu sahifadan ham ko'rish va
tasdiqlash mumkin; mantiq Telegram bilan bir xil servisdan olinadi.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from accounts.models import BranchRequest
from accounts.services import branch_requests as branch_service

superadmin_only = user_passes_test(lambda u: u.is_superuser)


def _so_rov_dict(so_rov: BranchRequest) -> dict:
    markaz = so_rov.created_center
    # "Nosoz" = tasdiqlangan deb belgilangan, lekin markaz yaratilmagan.
    # Bunday qatorlar Django admin'da `status` ni qo'lda o'zgartirishdan
    # qolgan (eski xatti-harakat). Ularni tuzatib qo'ysa bo'ladi.
    nosoz = (
        so_rov.status == BranchRequest.Status.APPROVED
        and so_rov.created_center_id is None
    )
    return {
        "id": so_rov.id,
        "nosoz": nosoz,
        "nom": so_rov.name,
        "manzil": so_rov.address or "—",
        "telefon": so_rov.phone or "—",
        "holat": so_rov.status,
        "holat_matni": so_rov.get_status_display(),
        "asosiy_markaz": so_rov.parent_center.name if so_rov.parent_center else "—",
        "sorovchi": so_rov.requester.get_full_name() or so_rov.requester.email,
        "sorovchi_email": so_rov.requester.email,
        "sana": so_rov.created_at.strftime("%d.%m.%Y %H:%M"),
        "korilgan": so_rov.reviewed_at.strftime("%d.%m.%Y %H:%M") if so_rov.reviewed_at else "",
        "yaratilgan_markaz": markaz.name if markaz else "",
        "yaratilgan_markaz_id": markaz.id if markaz else None,
        "rad_sababi": so_rov.reject_reason or "",
    }


@login_required
@superadmin_only
def superadmin_filiallar(request):
    """Filial so'rovlari ro'yxati."""
    qidiruv = (request.GET.get("q") or "").strip()

    so_rovlar = (
        BranchRequest.objects
        .select_related("requester", "parent_center", "created_center")
        .order_by("-created_at")
    )
    if qidiruv:
        so_rovlar = so_rovlar.filter(
            Q(name__icontains=qidiruv)
            | Q(parent_center__name__icontains=qidiruv)
            | Q(requester__email__icontains=qidiruv)
        )

    barchasi = [_so_rov_dict(s) for s in so_rovlar[:300]]
    kutilmoqda = [s for s in barchasi if s["holat"] == BranchRequest.Status.PENDING]

    return render(request, "accounts/superadmin_filiallar.html", {
        # DIQQAT: bu yerga `json.dumps(...)` BERILMAYDI. `json_script` filtri
        # o'zi serializatsiya qiladi — tayyor satr berilsa ikki marta kodlanib,
        # JS tomonda massiv o'rniga satr chiqadi va jadval bo'sh qoladi.
        "sorovlar": barchasi,
        "kutilmoqda_soni": len(kutilmoqda),
        "nosoz_soni": sum(1 for s in barchasi if s["nosoz"]),
        "jami_soni": len(barchasi),
        "tasdiqlangan_soni": sum(
            1 for s in barchasi if s["holat"] == BranchRequest.Status.APPROVED
        ),
        "rad_soni": sum(
            1 for s in barchasi if s["holat"] == BranchRequest.Status.REJECTED
        ),
        "qidiruv": qidiruv,
    })


@login_required
@superadmin_only
def branch_request_action(request, sorov_id: int):
    """So'rovni tasdiqlash yoki rad etish (AJAX)."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Faqat POST"}, status=405)

    so_rov = get_object_or_404(BranchRequest, pk=sorov_id)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        data = {}

    amal = (data.get("amal") or "").strip()

    try:
        if amal == "tasdiqla":
            markaz = branch_service.tasdiqla(so_rov, reviewer=request.user)
            return JsonResponse({
                "ok": True,
                "xabar": f"«{markaz.name}» filiali yaratildi.",
                "sorov": _so_rov_dict(
                    BranchRequest.objects.select_related(
                        "requester", "parent_center", "created_center"
                    ).get(pk=so_rov.pk)
                ),
            })

        if amal == "rad_et":
            branch_service.rad_et(
                so_rov, sabab=data.get("sabab") or "", reviewer=request.user
            )
            return JsonResponse({
                "ok": True,
                "xabar": "So'rov rad etildi.",
                "sorov": _so_rov_dict(
                    BranchRequest.objects.select_related(
                        "requester", "parent_center", "created_center"
                    ).get(pk=so_rov.pk)
                ),
            })
    except branch_service.FilialXatosi as xato:
        return JsonResponse({"ok": False, "error": str(xato)}, status=409)

    return JsonResponse({"ok": False, "error": "Noma'lum amal"}, status=400)
