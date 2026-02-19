from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and getattr(user, 'role', None) == 'student':
            self.fields['ism'].disabled = True
            self.fields['familya'].disabled = True
            # Optional: Add visual indication
            self.fields['ism'].widget.attrs['class'] += ' text-muted'
            self.fields['ism'].widget.attrs['readonly'] = True
            self.fields['familya'].widget.attrs['class'] += ' text-muted'
            self.fields['familya'].widget.attrs['readonly'] = True

    class Meta:
        model = User
        fields = ("avatar", "ism", "familya")
        widgets = {
            "avatar": forms.FileInput(attrs={
                "id": "id_avatar",
                "class": "file-input",
                "accept": "image/png,image/jpeg,image/webp",
            }),
            "ism": forms.TextInput(attrs={"class": "inp", "placeholder": "Ism"}),
            "familya": forms.TextInput(attrs={"class": "inp", "placeholder": "Familya"}),
        }

    def clean_avatar(self):
        f = self.cleaned_data.get("avatar")
        if not f:
            return f

        max_size = 4 * 1024 * 1024
        if f.size > max_size:
            raise forms.ValidationError("Rasm hajmi 4MB dan oshmasin.")

        allowed = {"image/png", "image/jpeg", "image/webp"}
        ct = getattr(f, "content_type", "")
        if ct and ct not in allowed:
            raise forms.ValidationError("Faqat JPG/PNG/WEBP ruxsat etiladi.")

        return f
