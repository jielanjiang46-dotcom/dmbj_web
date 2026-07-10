from django.urls import path
from . import views

app_name = 'zhang_jia'

urlpatterns = [
    path('memory/', views.memory, name='memory'),
    path('api/update-memory-score/', views.update_memory_score, name='api_update_memory_score'),
    path('api/get-memory-score/', views.get_memory_score, name='api_get_memory_score'),
    path('gu_lou/',views.gu_lou,name='gu_lou'),
    path('snake/', views.snake_game, name='snake'),
    path('api/snake_action/', views.api_snake_action, name='api_snake_action'),
    path('api/get-snake-score/', views.get_snake_score, name='get_snake_score'),
    path('api_snake_leaderboard/', views.api_snake_leaderboard, name='api_snake_leaderboard'),
    path('lobby/', views.game_lobby, name='game_lobby'),
    path('api/game/invite/', views.send_game_invite, name='send_game_invite'),
]