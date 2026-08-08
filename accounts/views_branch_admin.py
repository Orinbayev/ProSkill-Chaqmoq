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

from accounts.models import BranchRequest, User
from accounts.services import branch_requests as branch_service
from accounts.services.center_access import center_root_map, center_tree_ids

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
        # Filial qaysi direktorga biriktiriladi (bo'sh = so'rovchining o'ziga).
        "biriktirilgan_id": so_rov.target_director_id,
        "biriktirilgan": (
            (so_rov.target_director.get_full_name() or so_rov.target_director.email)
            if so_rov.target_director_id else ""
        ),
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
        .select_related(
            "requester", "parent_center", "created_center", "target_director",
        )
        .order_by("-created_at")
    )
    if qidiruv:
        so_rovlar = so_rovlar.filter(
            Q(name__icontains=qidiruv)
            | Q(parent_center__name__icontains=qidiruv)
            | Q(requester__email__icontains=qidiruv)
        )

    ro_yxat = list(so_rovlar[:300])
    barchasi = [_so_rov_dict(s) for s in ro_yxat]
    kutilmoqda = [s for s in barchasi if s["holat"] == BranchRequest.Status.PENDING]

    # ── Har so'rov uchun "biriktirish mumkin" direktorlar ────────────────
    # Filial faqat O'Z markaz daraxtidagi direktorga biriktiriladi (cross-tenant
    # ruxsat = IDOR). Xarita + bitta direktor so'rovi = N+1 yo'q.
    root_xarita = center_root_map()
    direktorlar = list(
        User.objects.filter(role="director", center__isnull=False, is_deleted=False)
        .only("id", "ism", "familya", "email", "center_id")
    )
    root_boyicha: dict[int, list[dict]] = {}
    for d in direktorlar:
        root_id = root_xarita.get(d.center_id)
        if root_id is None:
            continue
        root_boyicha.setdefault(root_id, []).append({
            "id": d.id,
            "nom": d.get_full_name() or d.email,
            "email": d.email,
        })

    for so_rov_obj, karta in zip(ro_yxat, barchasi):
        root_id = root_xarita.get(so_rov_obj.parent_center_id)
        karta["nomzod_direktorlar"] = root_boyicha.get(root_id, [])

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


def _biriktirilgan_direktorni_belgila(so_rov: BranchRequest, direktor_id) -> str | None:
    """`target_director` ni tekshirib belgilaydi. Xato matnini qaytaradi (yoki None).

    XAVFSIZLIK: direktor faqat so'rovning O'Z markaz daraxtidan bo'lishi shart.
    Aks holda superadmin xato bosib, boshqa mijozning direktoriga begona
    filialga ruxsat bergan bo'lib qolardi (cross-tenant IDOR).
    """
    if direktor_id in (None, "", 0, "0"):
        return None

    try:
        direktor_id = int(direktor_id)
    except (TypeError, ValueError):
        return "direktor_id noto'g'ri."

    direktor = User.objects.filter(
        pk=direktor_id, role="director", is_deleted=False
    ).select_related("center").first()
    if direktor is None:
        return "Direktor topilmadi."
    if direktor.center_id is None:
        return "Bu direktorga asosiy markaz belgilanmagan."

    if so_rov.parent_center_id is None:
        return "So'rovning asosiy markazi topilmadi."

    ruxsat_etilgan = center_tree_ids(so_rov.parent_center)
    if direktor.center_id not in ruxsat_etilgan:
        return "Bu direktor boshqa markaz daraxtiga tegishli — biriktirib bo'lmaydi."

    if so_rov.target_director_id != direktor_id:
        so_rov.target_director_id = direktor_id
        so_rov.save(update_fields=["target_director"])
    return None


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
            # Ixtiyoriy: filialni BOSHQA direktorga biriktirish.
            # Bo'sh bo'lsa — eski xatti-harakat (so'rovchining o'ziga).
            xato = _biriktirilgan_direktorni_belgila(so_rov, data.get("direktor_id"))
            if xato:
                return JsonResponse({"ok": False, "error": xato}, status=400)

            markaz = branch_service.tasdiqla(so_rov, reviewer=request.user)
            return JsonResponse({
                "ok": True,
                "xabar": f"«{markaz.name}» filiali yaratildi.",
                "sorov": _so_rov_dict(
                    BranchRequest.objects.select_related(
                        "requester", "parent_center", "created_center",
                        "target_director",
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
                        "requester", "parent_center", "created_center",
                        "target_director",
                    ).get(pk=so_rov.pk)
                ),
            })
    except branch_service.FilialXatosi as xato:
        return JsonResponse({"ok": False, "error": str(xato)}, status=409)

    return JsonResponse({"ok": False, "error": "Noma'lum amal"}, status=400)
