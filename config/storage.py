# config/storage.py
"""
Custom static files storage for production (WhiteNoise + Render).

MUAMMO:
  django-jazzmin paketi vendor/bootstrap/js/bootstrap.bundle.min.js faylini
  o'z ichiga oladi, lekin bu fayl oxirida:
      //# sourceMappingURL=bootstrap.bundle.min.js.map
  degan qator bor. Lekin jazzmin paketida shu .map fayl YO'Q.

  Xuddi shunga o'xshash holat local bootstrap CSS faylida ham bor:
      /*# sourceMappingURL=bootstrap.min.css.map */
  Lekin .map fayl repositoryga kiritilmagan.

  collectstatic --noinput paytida CompressedManifestStaticFilesStorage
  CSS/JS sourceMappingURL kommentlarini topib, u fayllarni
  hash-substitute qilmoqchi bo'ladi. .map fayl topilmagani uchun:
      whitenoise.storage.MissingFileError
  xatoligi chiqib, build yiqiladi.

YECHIM:
  CSS va JS fayllardagi sourceMappingURL pattern-larini collectstatic
  post-process bosqichidan chiqarib tashlaymiz.
  CSS URL/import pattern-lari o'z joyida qoladi.
  Bu production uchun xavfsiz: .map fayllar faqat debug uchun kerak,
  brauzer ular bo'lmasa ham to'g'ri ishlaydi.
"""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class CustomManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    WhiteNoise CompressedManifestStaticFilesStorage — CSS/JS sourceMappingURL
    ishlov berish o'chirilgan versiyasi.

    Bootstrap JS va CSS fayllarida .map reference bor, lekin
    .map fayllar repository/paketga kiritilmagan. Bu MissingFileError-ni
    oldini oladi.

    CSS fayllardagi url() va @import qatorlari hali ham to'g'ri
    hash-substitute qilinadi.

    manifest_strict=False: Jazzmin bootswatch tema fayllari (vendor/bootswatch/*)
    manifest'da topilmasa ham 500 xato bermaydi — unhashed URL qaytaradi.
    """
    manifest_strict = False

    # Django 5.0 default patterns-dan *.js bloki olib tashlangan.
    # *.css bloki to'liq saqlanib qolgan.
    patterns = (
        (
            "*.css",
            (
                r"(?P<matched>url\(['\"]?(?P<url>[^)]+?)['\"]?\))",
                (
                    r"(?P<matched>@import\s*['\"](?P<url>[^'\"]+)['\"])",
                    '@import url("%(url)s")',
                ),
            ),
        ),
        # *.js pattern intentionally omitted:
        # Prevents MissingFileError caused by JS files referencing .map files
        # that are not shipped with the package/repository.
        # Source maps are developer tools only — not needed in production.
    )
