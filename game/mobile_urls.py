from django.urls import path

from . import mobile_api


urlpatterns = [
    # Ro'yxatdan o'tish (ChaqmoqApp hisobi bo'lmaganlar uchun).
    path("register/", mobile_api.game_register, name="game_register"),

    # Google orqali kirish (markazsiz o'yinchi)
    path("auth/google/", mobile_api.game_google_login, name="game_google_login"),
    path("auth/profile/", mobile_api.game_profile_setup, name="game_profile_setup"),
    path("me/", mobile_api.game_my_profile, name="game_my_profile"),

    path("home/", mobile_api.game_home, name="game_home"),

    # O'yinlar katalogi — admin paneldagi o'yinlar shu yerdan keladi.
    path("catalog/", mobile_api.game_catalog, name="game_catalog"),
    path("play/<int:mode_id>/start/", mobile_api.game_play_start, name="game_play_start"),
    path(
        "play/session/<int:sessiya_id>/answer/",
        mobile_api.game_session_answer,
        name="game_session_answer",
    ),
    path(
        "play/session/<int:sessiya_id>/finish/",
        mobile_api.game_session_finish,
        name="game_session_finish",
    ),
    path("play/history/", mobile_api.game_session_history, name="game_session_history"),

    # Real duel — raqib qidirish navbati
    path("queue/<int:navbat_id>/", mobile_api.game_queue_status, name="game_queue_status"),
    path("queue/<int:navbat_id>/robot/", mobile_api.game_queue_robot, name="game_queue_robot"),
    path("queue/<int:navbat_id>/cancel/", mobile_api.game_queue_cancel, name="game_queue_cancel"),

    # Shikoyat va takliflar
    path("feedback/", mobile_api.game_feedback_list, name="game_feedback_list"),
    path("feedback/send/", mobile_api.game_feedback_send, name="game_feedback_send"),

    # Duel
    path("duel/start/", mobile_api.game_duel_start, name="game_duel_start"),
    path("duel/<int:duel_id>/answer/", mobile_api.game_duel_answer, name="game_duel_answer"),
    path("duel/<int:duel_id>/finish/", mobile_api.game_duel_finish, name="game_duel_finish"),
    path("duel/history/", mobile_api.game_duel_history, name="game_duel_history"),

    path("league/", mobile_api.game_league, name="game_league"),
    path("news/", mobile_api.game_news, name="game_news"),

    # Do'kon
    path("shop/", mobile_api.game_shop, name="game_shop"),
    path("shop/<int:item_id>/buy/", mobile_api.game_shop_buy, name="game_shop_buy"),
    path("purchases/", mobile_api.game_purchases, name="game_purchases"),

    path("tariffs/", mobile_api.game_tariffs, name="game_tariffs"),
    path("tariffs/<int:tarif_id>/buy/", mobile_api.game_tariff_buy, name="game_tariff_buy"),
    path("tariffs/requests/", mobile_api.game_tariff_requests, name="game_tariff_requests"),

    # Profil
    path("profile/", mobile_api.game_profile, name="game_profile"),
    path("profile/avatar/", mobile_api.game_avatar, name="game_avatar"),
    path("users/<int:user_id>/", mobile_api.game_user_profile, name="game_user_profile"),
    path("users/search/", mobile_api.game_search_users, name="game_search_users"),
    path("online/", mobile_api.game_online, name="game_online"),

    # Do'stlar
    path("friends/", mobile_api.game_friends, name="game_friends"),
    path("friends/<int:user_id>/request/", mobile_api.game_friend_request, name="game_friend_request"),
    path("friends/<int:friendship_id>/respond/", mobile_api.game_friend_respond, name="game_friend_respond"),

    # Duelga chaqiriq
    path("invites/", mobile_api.game_invites, name="game_invites"),
    path("invites/<int:user_id>/send/", mobile_api.game_invite, name="game_invite"),
    path("invites/<int:invite_id>/respond/", mobile_api.game_invite_respond, name="game_invite_respond"),
]
