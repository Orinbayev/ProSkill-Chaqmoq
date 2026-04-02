# config/storage.py
"""
Custom static files storage for production (WhiteNoise + Render).

MUAMMO:
  django-jazzmin paketi vendor/bootstrap/js/bootstrap.bundle.min.js faylini
  o'z ichiga oladi, lekin bu fayl oxirida:
      //# sourceMappingURL=bootstrap.bundle.min.js.map
  degan qator bor. Lekin jazzmin paketida shu .map fayl YO'Q.

  collectstatic --noinput paytida CompressedManifestStaticFilesStorage
  har bir JS faylidagi sourceMappingURL kommentini topib, u faylni
  hash-substitute qilmoqchi bo'ladi. .map fayl topilmagani uchun:
      whitenoise.storage.MissingFileError
  xatoligi chiqib, build yiqiladi.

YECHIM:
  JS fayllaridagi sourceMappingURL pattern-ni o'chirib qo'yamiz.
  CSS URL/import pattern-lari o'z joyida qoladi.
  Bu production uchun xavfsiz: .map fayllar faqat debug uchun kerak,
  brauzer ular bo'lmasa ham to'g'ri ishlaydi.
"""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class CustomManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    WhiteNoise CompressedManifestStaticFilesStorage — JS sourceMappingURL
    ishlov berish o'chirilgan versiyasi.

    Jazzmin's bootstrap.bundle.min.js faylida .map reference bor, lekin
    .map fayl paketga kiritilmagan. Bu MissingFileError-ni oldini oladi.

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
                (
                    r'(?m)^(?P<matched>/\*#[ \t](?-i:sourceMappingURL)=(?P<url>.*)[ \t]*\*/)$',
                    "/*# sourceMappingURL=%(url)s */",
                ),
            ),
        ),
        # *.js pattern intentionally omitted:
        # Prevents MissingFileError caused by jazzmin's bootstrap.bundle.min.js
        # referencing a .map file that is not shipped with the jazzmin package.
        # Source maps are developer tools only — not needed in production.
    )
