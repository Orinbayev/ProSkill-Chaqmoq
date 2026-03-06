
# from django.utils.http import escape_leading_slashes
# from operator import truediv
# salat =  True
# choy = False
# manti = True
# besh_barmoq = True
# palov = False
# desert = True
# boliq = False

# narh = 10000
# if salat:
#     print("Mijoz siz salat zakaz qildingiz")
#     narh = narh + 30000
# if choy:
#     print("Mijoz siz choy zakaz qildingiz")
#     narh = narh + 10000
# if manti:
#     print("Mijoz siz manti zakaz qildingiz")
#     narh = narh + 45000
# if besh_barmoq:
#     print("Mijoz siz besh_barmoq zakaz qildingiz")
#     narh = narh + 80000
# if palov:
#     print("Mijoz siz palov zakaz qildingiz")
#     narh = narh + 40000
# if desert:
#     print("Mijoz siz desert zakaz qildingiz")
#     narh = narh + 35000
# if boliq:
#     print("Mijoz siz boliq zakaz qildingiz")
#     narh = narh + 90000
# else:
#     print("Siz ro'za siz!!")

# print(f"Jami narx: {narh} so'm")

# if choy and salat:
#     narh += 20000
# elif choy or salat:
#     narh += 10000
# else:
#     narh += 0
#     print("Mijoz xech nima yemgan!")

# print(f"Jami narx: {narh} so'm")



taomlar = ["salat", "choy", "manti", "besh_barmoq", "palov", "desert", "boliq"]

mijoz = []

if mijoz:
    for taom in taomlar:
        if taom not in mijoz:
            print(f"Mijoz siz {taom} zakaz qilmadingiz")
            
        else:
            print(f"Mijoz siz {taom} zakaz qildingiz")
else:
    print("Mijoz xech nima yemgan!")

# menu = ['osh','qazonkabob','shashlik','norin','somsa']

# ovqat = input('Nima ovqat yeysiz?>>> ')
# if ovqat.lower() not in menu:
#     print('Afsuski bizda bunday ovqat yo\'q')
# else:
#     print('Buyurtma qabul qilindi.')